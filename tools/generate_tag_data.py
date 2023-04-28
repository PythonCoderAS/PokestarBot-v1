#!/usr/bin/env pipenv run python

import asyncio

import aiohttp

from bot_data.utils.data.mangadex.tag import Tag


async def main():
    async with aiohttp.ClientSession() as session:
        async with session.get("https://mangadex.org/api/v2/tag") as request:
            json = await request.json()
    data = {}
    for item in json["data"].values():
        tag = Tag(**item)
        data[tag.id] = tag
    print("data = {" + ",\n".join(f"{num}: {item._full_repr()}" for num, item in data.items()) + "}")


if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
