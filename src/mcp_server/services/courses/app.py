import aiohttp
from fastmcp import FastMCP

BASE_URL = "https://course-tools.apis.scottylabs.org"
TIMEOUT = aiohttp.ClientTimeout(total=10)

app = FastMCP("cmucourses-proxy")

# --- Internal HTTP helpers ---
async def _get_http(path: str, params: dict | None = None) -> dict:
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        async with session.get(f"{BASE_URL}{path}", params=params, ssl=False) as resp:
            resp.raise_for_status()
            return await resp.json()

async def _post_http(path: str, data: dict | None = None) -> dict:
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        async with session.post(f"{BASE_URL}{path}", json=data, ssl=False) as resp:
            resp.raise_for_status()
            return await resp.json()

# --- Internal helpers for per-course data ---
async def _get_instructors_for_course(course_id: str) -> list[str]:
    course_data = await _get_courses(course_ids=[course_id], schedules=True)
    instructors = []
    for course in course_data:
        for sched in course.get("schedules", []):
            if "instructor" in sched:
                instructors.append(sched["instructor"])
    return list(set(instructors))

async def _get_schedules_for_course(course_id: str) -> list[dict]:
    course_data = await _get_courses(course_ids=[course_id], schedules=True)
    if course_data and "schedules" in course_data[0]:
        return course_data[0]["schedules"]
    return []

# --- Core API functions (can be called internally) ---
async def _get_courses(course_ids: list[str] | None = None, schedules: bool = False) -> list[dict]:
    params = {}
    if course_ids:
        params["courseID"] = course_ids
    if schedules:
        params["schedules"] = "true"
    return await _get_http("/courses", params=params)

async def _get_course(course_id: str) -> dict:
    return await _get_http(f"/course/{course_id}")

async def _get_all_courses() -> list[dict]:
    return await _get_http("/courses/all")

async def _get_requisites(course_id: str) -> dict:
    return await _get_http(f"/courses/requisites/{course_id}")

async def _search_courses(query: str) -> list[dict]:
    return await _get_http("/courses/search/", params={"query": query})

async def _post_search_courses(user_token: str, query: str) -> dict:
    return await _post_http("/courses/search/", data={"token": user_token, "query": query})

async def _get_instructors() -> list[dict]:
    return await _get_http("/instructors")

async def _get_schedules() -> list[dict]:
    return await _get_http("/schedules")

# --- MCP Tools ---
@app.tool()
async def get_course_tool(course_id: str) -> dict:
    return await _get_course(course_id)

@app.tool()
async def get_courses_tool(course_ids: list[str] | None = None, schedules: bool = False) -> list[dict]:
    return await _get_courses(course_ids=course_ids, schedules=schedules)

@app.tool()
async def post_courses_tool(user_token: str, course_ids: list[str] | None = None) -> dict:
    data = {"token": user_token}
    if course_ids:
        data["courseID"] = course_ids
    return await _post_http("/courses", data=data)

@app.tool()
async def get_all_courses_tool() -> list[dict]:
    return await _get_all_courses()

@app.tool()
async def get_requisites_tool(course_id: str) -> dict:
    return await _get_requisites(course_id)

@app.tool()
async def search_courses_tool(query: str) -> list[dict]:
    return await _search_courses(query)

@app.tool()
async def post_search_courses_tool(user_token: str, query: str) -> dict:
    return await _post_search_courses(user_token, query)

@app.tool()
async def get_instructors_tool() -> list[dict]:
    return await _get_instructors()

@app.tool()
async def get_schedules_tool() -> list[dict]:
    return await _get_schedules()

# --- MCP Tools for per-course helpers ---
@app.tool()
async def get_instructors_for_course(course_id: str) -> list[str]:
    return await _get_instructors_for_course(course_id)

@app.tool()
async def get_schedules_for_course(course_id: str) -> list[dict]:
    return await _get_schedules_for_course(course_id)

@app.tool()
async def list_tools() -> list[str]:
    return list(app.tools.keys())


# --- Run server ---
if __name__ == "__main__":
    app.run()
