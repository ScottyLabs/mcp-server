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

async def _get_requisites(course_id: str) -> dict:
    return await _get_http(f"/courses/requisites/{course_id}")

async def _search_courses(query: str) -> list[dict]:
    return await _get_http("/courses", params={"courseID": query})

# async def _get_instructors() -> list[dict]:
#     return await _get_http("/instructors")

# async def _get_schedules() -> list[dict]:
#     return await _get_http("/schedules")

async def _get_geneds(school: str | None = None, user_token: str | None = None) -> list[dict]:
    """
    Fetch general education requirements. Supports optional school query param (e.g., "SCS").
    If user_token provided, does POST, else GET.
    """
    if user_token and user_token.strip():
        data = {"token": user_token}
        if school:
            data["school"] = school
        return await _post_http("/geneds", data=data)
    else:
        params = {}
        if school:
            params["school"] = school
        return await _get_http("/geneds", params=params)

async def _get_geneds_for_department(department: str, school: str | None = None, user_token: str | None = None) -> list[dict]:
    """
    Fetch geneds filtered by department and optional school.
    """
    geneds = await _get_geneds(school=school, user_token=user_token)
    allowed_geneds = []
    for g in geneds:
        departments = g.get("departments", [])
        if not departments or department in departments:
            allowed_geneds.append(g)
    return allowed_geneds


# --- MCP Tools ---
@app.tool()
async def fetch_course_by_id(course_id: str) -> dict:
    """Fetch a CMU course by its ID (exact match, e.g. "15-122" or "15-213")."""
    return await _get_course(course_id)

@app.tool()
async def fetch_courses_by_ids(course_ids: list[str] | None = None, schedules: bool = False) -> list[dict]:
    """Fetch a list of CMU courses by their IDs (exact match, e.g. ["15-122", "15-213"])."""
    return await _get_courses(course_ids=course_ids, schedules=schedules)

@app.tool()
async def fetch_course_requisites(course_id: str) -> dict:
    """Fetch the requisites for a CMU course by its ID (exact match)."""
    return await _get_requisites(course_id)

@app.tool()
async def search_courses_by_query(query: str) -> list[dict]:
    """Search for CMU courses by name or description (e.g. "programming" or "database")."""
    return await _search_courses(query)

# --- MCP Tools for per-course helpers ---
@app.tool()
async def fetch_course_instructors(course_id: str) -> list[str]:
    """Fetch all instructors for a CMU course by its ID (exact match)."""
    return await _get_instructors_for_course(course_id)

@app.tool()
async def fetch_course_schedules(course_id: str) -> list[dict]:
    """Fetch all schedules/times for a CMU course by its ID (exact match)."""
    return await _get_schedules_for_course(course_id)


@app.tool()
async def fetch_geneds_tool(school: str | None = None, user_token: str | None = None) -> list[dict]:
    """
    Fetch all general education requirements, optionally filtered by school.
    """
    return await _get_geneds(school=school, user_token=user_token)

@app.tool()
async def fetch_geneds_for_department_tool(department: str, school: str | None = None, user_token: str | None = None) -> list[dict]:
    """
    Fetch general education requirements allowed for a specific department,
    optionally filtered by school and requiring a user token.
    """
    return await _get_geneds_for_department(department=department, school=school, user_token=user_token)


# --- Run server ---
if __name__ == "__main__":
    app.run()
