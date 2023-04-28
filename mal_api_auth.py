#!/usr/bin/env pipenv run python

import asyncio
import secrets
import sys

import aiohttp.web


class Authenticator:
    @property
    def get_token(self) -> str:
        token = secrets.token_urlsafe(100)
        return token[:128]

    @property
    def user_url(self):
        return f"https://myanimelist.net/v1/oauth2/authorize?response_type={self.response_type}&client_id={self.client_id}&code_challenge=" \
               f"{self.code_verifier}&state={self.state}"

    def __init__(self):
        self.client_secret = self.client_id = ""
        self.response_type = "code"
        self.code_verifier = self.get_token
        self.state = self.get_token

    async def _exit(self):
        await asyncio.sleep(5)
        sys.exit(0)

    async def handler(self, request: aiohttp.web.Request):
        data = request.query
        state = data.getone("state")
        assert state == self.state, "Bad request."
        code = data.getone("code")
        print("Code: ", code)
        async with aiohttp.ClientSession() as session:
            async with session.post("https://myanimelist.net/v1/oauth2/token", data={
                "client_id": self.client_id, "client_secret": self.client_secret, "code": code, "code_verifier": self.code_verifier,
                "grant_type": "authorization_code"
            }) as request2:
                json = await request2.json()
        refresh_token = json.get("refresh_token", None)
        if refresh_token is None:
            print("Error! JSON: ", json)
            return aiohttp.web.Response(body=f'<p>Error!: <code style="background-color: B0B0B0">{json}</code></p>',
                                        content_type="text/html", status=500)
        print("Refresh Token:", refresh_token)
        return aiohttp.web.Response(body=f'<p>Refresh Token: <code style="background-color: B0B0B0">{refresh_token}</code></p>',
                                    content_type="text/html")

    def start(self):
        self.client_id = input("Client ID: ")
        self.client_secret = input("Client Secret: ")
        print("Click on this URL to complete:", self.user_url)
        app = aiohttp.web.Application()
        app.add_routes([aiohttp.web.route("*", "/oauth", self.handler)])
        aiohttp.web.run_app(app, port=8000)


def main():
    Authenticator().start()
    sys.exit(0)


if __name__ == '__main__':
    main()
