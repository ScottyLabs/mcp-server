import os
import re
import time
from dataclasses import dataclass, field

import aiohttp
from fastmcp import FastMCP

# Only these paths in the repo hold actual guide content; the rest is site framework/config.
CONTENT_ROOTS = ("src/pages", "README.md")

TREE_URL = f"https://api.github.com/repos/ScottyLabs/cmu-guide/git/trees/main?recursive=1"
RAW_URL = f"https://raw.githubusercontent.com/ScottyLabs/cmu-guide/main/{{path}}"
BLOB_URL = f"https://github.com/ScottyLabs/cmu-guide/blob/main/{{path}}"

TIMEOUT = aiohttp.ClientTimeout(total=15)
CACHE_TTL_SECONDS = 24 * 60 * 60  # 24h
GITHUB_HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": "cmu-guide-mcp"}
if os.environ.get("GITHUB_TOKEN"):
    GITHUB_HEADERS["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"

app = FastMCP("cmu-guide-proxy")

TOKEN_RE = re.compile(r"[a-z0-9]+")
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)
HEADING_RE = re.compile(r"^(#{2,3})\s+(.*)$")


@dataclass
class Page:
    path: str
    title: str
    description: str
    raw_content: str


@dataclass
class Chunk:
    id: str
    file: str
    title: str
    heading: str
    heading_path: str
    content: str
    url: str
    tokens: list[str] = field(default_factory=list)


class GuideIndex:
    def __init__(self) -> None:
        self.pages: list[Page] = []
        self.chunks: list[Chunk] = []
        self.built_at: float = 0.0

    def is_stale(self) -> bool:
        return (time.time() - self.built_at) > CACHE_TTL_SECONDS

    async def ensure_loaded(self) -> None:
        if not self.chunks or self.is_stale():
            await self.rebuild()

    async def rebuild(self) -> None:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
            paths = await _fetch_content_paths(session)
            pages: list[Page] = []
            chunks: list[Chunk] = []
            for p in paths:
                raw = await _fetch_raw(session, p)
                title, description, body = _parse_frontmatter(p, raw)
                pages.append(Page(path=p, title=title, description=description, raw_content=raw))
                chunks.extend(_chunk_markdown(p, title, body))
        self.pages = pages
        self.chunks = chunks
        self.built_at = time.time()

    def get_page(self, path: str) -> Page | None:
        return next((p for p in self.pages if p.path == path), None)

    def get_chunk(self, chunk_id: str) -> Chunk | None:
        return next((c for c in self.chunks if c.id == chunk_id), None)

    def search(self, query: str, limit: int = 5) -> list[tuple[Chunk, float]]:
        query_tokens = TOKEN_RE.findall(query.lower())
        if not query_tokens:
            return []
        scored: list[tuple[Chunk, float]] = []
        for chunk in self.chunks:
            score = 0.0
            title_tokens = TOKEN_RE.findall(chunk.title.lower())
            heading_tokens = TOKEN_RE.findall(chunk.heading.lower())
            for qt in query_tokens:
                score += chunk.tokens.count(qt) * 1.0
                score += title_tokens.count(qt) * 3.0
                score += heading_tokens.count(qt) * 2.0
                # light partial-match credit so e.g. "refund" still hits "refunds"
                if score == 0 and any(qt in t for t in chunk.tokens):
                    score += 0.3
            if score > 0:
                scored.append((chunk, score))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:limit]


_index = GuideIndex()


# --- Internal HTTP / parsing helpers ---

async def _fetch_content_paths(session: aiohttp.ClientSession) -> list[str]:
    async with session.get(TREE_URL, headers=GITHUB_HEADERS, ssl=False) as resp:
        resp.raise_for_status()
        data = await resp.json()
    paths = [
        entry["path"]
        for entry in data.get("tree", [])
        if entry.get("type") == "blob"
        and (entry["path"].endswith(".md") or entry["path"].endswith(".mdx"))
    ]
    return [p for p in paths if any(p == root or p.startswith(root + "/") for root in CONTENT_ROOTS)]


async def _fetch_raw(session: aiohttp.ClientSession, path: str) -> str:
    async with session.get(RAW_URL.format(path=path), ssl=False) as resp:
        resp.raise_for_status()
        return await resp.text()


def _parse_frontmatter(path: str, raw: str) -> tuple[str, str, str]:
    title = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    description = ""
    body = raw
    match = FRONTMATTER_RE.match(raw)
    if match:
        body = raw[match.end():]
        for line in match.group(1).splitlines():
            if line.startswith("title:"):
                title = line.split(":", 1)[1].strip().strip("'\"")
            elif line.startswith("description:"):
                description = line.split(":", 1)[1].strip().strip("'\"")
    return title, description, body


def _chunk_markdown(path: str, title: str, body: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    heading, level, buf, idx = "(intro)", 0, [], 0

    def flush() -> None:
        nonlocal idx, buf
        content = "\n".join(buf).strip()
        if content:
            idx += 1
            heading_path = f"{title} > {heading}" if level else title
            chunks.append(
                Chunk(
                    id=f"{path}#{idx}",
                    file=path,
                    title=title,
                    heading=heading,
                    heading_path=heading_path,
                    content=content,
                    url=BLOB_URL.format(path=path),
                    tokens=TOKEN_RE.findall(content.lower()),
                )
            )
        buf = []

    for line in body.splitlines():
        m = HEADING_RE.match(line)
        if m:
            flush()
            level, heading = len(m.group(1)), m.group(2).strip()
            continue
        buf.append(line)
    flush()
    return chunks


def _truncate(text: str, max_len: int = 600) -> str:
    return text if len(text) <= max_len else text[:max_len].rstrip() + "\u2026"


# --- MCP Tools ---

@app.tool()
async def search_guide(query: str, limit: int = 5) -> list[dict]:
    """
    Full-text search over the ScottyLabs cmu-guide (cmu.guide) — dorms, meal plans, leaves of
    absence, transferring majors, accommodations, etc. Returns short snippets with a chunk_id
    and source file for each match. Use get_section or get_page to pull the full text of a
    specific result once you know which one you need; don't load whole pages up front.
    """
    await _index.ensure_loaded()
    results = _index.search(query, limit=limit)
    return [
        {
            "chunk_id": chunk.id,
            "file": chunk.file,
            "heading_path": chunk.heading_path,
            "snippet": _truncate(chunk.content),
            "score": round(score, 2),
        }
        for chunk, score in results
    ]


@app.tool()
async def get_section(chunk_id: str) -> dict:
    """Fetch the full text of one chunk/section returned by search_guide, by its chunk_id
    (e.g. "src/pages/loareturn.md#3")."""
    await _index.ensure_loaded()
    chunk = _index.get_chunk(chunk_id)
    if chunk is None:
        return {"error": f'No chunk found with id "{chunk_id}".'}
    return {
        "heading_path": chunk.heading_path,
        "url": chunk.url,
        "content": chunk.content,
    }


@app.tool()
async def get_page(path: str) -> dict:
    """Fetch the complete raw markdown of a single page from the guide, by its repo path
    (e.g. "src/pages/meal-plans.md"). Use list_pages to see valid paths. Prefer search_guide +
    get_section for targeted lookups; use this only when you actually need the whole page."""
    await _index.ensure_loaded()
    page = _index.get_page(path)
    if page is None:
        return {"error": f'No page found at "{path}". Use list_pages to see valid paths.'}
    return {"path": page.path, "title": page.title, "content": page.raw_content}


@app.tool()
async def list_pages() -> list[dict]:
    """List every page in the cmu-guide with its title, description, and repo path. Good
    starting point to see what topics are covered before searching or fetching."""
    await _index.ensure_loaded()
    return [{"path": p.path, "title": p.title, "description": p.description} for p in _index.pages]


@app.tool()
async def refresh_index() -> dict:
    """Re-fetch the latest content from github.com/ScottyLabs/cmu-guide and rebuild the search
    index. The index is normally cached for 24h in memory, so call this if the guide may have
    been updated and you need fresh content."""
    await _index.rebuild()
    return {"pages": len(_index.pages), "chunks": len(_index.chunks)}


# --- Run the FastMCP server ---
if __name__ == "__main__":
    app.run()