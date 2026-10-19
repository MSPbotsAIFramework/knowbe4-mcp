# Copyright 2026 MSPbots.ai
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Credential middleware: 401 / 400 on bad headers, region, per-request isolation."""

import asyncio

import pytest
from starlette.testclient import TestClient

from knowbe4_mcp.__main__ import build_http_app
from knowbe4_mcp.server import GatewayCredentialsMiddleware, _credentials_var, create_mcp_server, get_client_from_context, normalize_region

MCP_HEADERS = {"Accept": "application/json, text/event-stream"}
LIST_TOOLS = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
CREDS = {"X-KnowBe4-API-Key": "key"}


def _client() -> TestClient:
    return TestClient(build_http_app(create_mcp_server()))


def test_health_is_local():
    with _client() as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.parametrize("headers", [{}, {"X-KnowBe4-API-Key": " "}, {"X-KnowBe4-API-Key": "${KB4_KEY}"}, {"X-KnowBe4-Region": "us"}])
def test_missing_key_returns_401(headers):
    with _client() as client:
        resp = client.post("/mcp", json=LIST_TOOLS, headers=MCP_HEADERS | headers)
    assert resp.status_code == 401
    assert resp.json()["required_headers"] == ["X-KnowBe4-API-Key"]


def test_unknown_region_returns_400():
    with _client() as client:
        resp = client.post("/mcp", json=LIST_TOOLS, headers=MCP_HEADERS | CREDS | {"X-KnowBe4-Region": "apac"})
    assert resp.status_code == 400


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, "us"),
        ("", "us"),
        ("EU", "eu"),
        ("ca.api.knowbe4.com", "ca"),
        ("https://uk.knowbe4.com/", "uk"),
        ("https://training.knowbe4.com", "us"),
        ("de", "de"),
        ("apac", None),
    ],
)
def test_normalize_region(value, expected):
    assert normalize_region(value) == expected


def test_tools_list_over_http():
    with _client() as client:
        resp = client.post("/mcp", json=LIST_TOOLS, headers=MCP_HEADERS | CREDS)
    assert resp.status_code == 200
    for name in ("knowbe4_users_list", "knowbe4_reporting_risk_overview", "knowbe4_policies_get"):
        assert name in resp.text


async def _receive():
    return {"type": "http.request", "body": b"", "more_body": False}


async def _send(_message):
    return None


def _run_middleware(headers: list[tuple[bytes, bytes]]) -> dict:
    seen: dict = {}

    async def app(scope, receive, send):
        seen["credentials"] = _credentials_var.get()
        seen["client"] = get_client_from_context()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    asyncio.run(GatewayCredentialsMiddleware(app)({"type": "http", "path": "/mcp", "headers": headers}, _receive, _send))
    return seen


def test_key_and_region_reach_context_and_are_reset():
    seen = _run_middleware([(b"x-knowbe4-api-key", b" key-123 "), (b"x-knowbe4-region", b"EU")])
    assert seen["client"]._headers()["Authorization"] == "Bearer key-123"
    assert seen["client"].base_url == "https://eu.api.knowbe4.com"
    assert _credentials_var.get() is None


def test_concurrent_requests_do_not_share_credentials():
    observed: list[tuple[str, str]] = []

    async def app(scope, receive, send):
        before = _credentials_var.get().api_key
        await asyncio.sleep(0.01)
        observed.append((before, _credentials_var.get().api_key))
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    middleware = GatewayCredentialsMiddleware(app)

    def scope(key: bytes) -> dict:
        return {"type": "http", "path": "/mcp", "headers": [(b"x-knowbe4-api-key", key)]}

    async def both():
        await asyncio.gather(middleware(scope(b"tenant-a"), _receive, _send), middleware(scope(b"tenant-b"), _receive, _send))

    asyncio.run(both())
    assert sorted(observed) == [("tenant-a", "tenant-a"), ("tenant-b", "tenant-b")]


def test_credentials_repr_hides_key():
    seen = _run_middleware([(b"x-knowbe4-api-key", b"very-secret-key")])
    assert "very-secret-key" not in repr(seen["credentials"])
