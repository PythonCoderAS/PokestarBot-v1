import asyncio
import datetime

import aiohttp

from ..const import GITHUB_HEADERS
from ..creds import owner, repo


async def post_issue(session: aiohttp.ClientSession, title: str, body: str = "") -> int:
    url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    params = {"title": title, "body": body}
    if getattr(session, "x_ratelimit_remaining", None) == 0:
        diff = session.x_ratelimit_reset - datetime.datetime.utcnow().timestamp()
        await asyncio.sleep(diff + 1)
    async with session.post(url, json=params, headers=GITHUB_HEADERS) as request:
        resp = await request.json()
        if request.status // 100 in [4, 5]:
            if request.status == 403 and request.headers.get("Retry-After", ""):
                num = int(request.headers["Retry-After"])
                await asyncio.sleep(num + 1)
                return await post_issue(session, title, body=body)
            raise aiohttp.ClientResponseError(aiohttp.RequestInfo(request.url, request.method, request.headers, request.real_url), (request,),
                                              status=request.status, message=str(resp))
        session.x_ratelimit_remaining = request.headers["X-RateLimit-Remaining"]
        session.x_ratelimit_reset = int(request.headers["X-RateLimit-Reset"])
        return int(resp["number"])
