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
"""FastMCP factory and the per-request credential middleware."""

import contextvars
import re
import uuid
from collections.abc import Callable

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .api_client import KnowBe4Client, KnowBe4Credentials
from .config import DEFAULT_REGION, REGION_BASE_URLS, Settings

HEADER_API_KEY = "X-KnowBe4-API-Key"
HEADER_REGION = "X-KnowBe4-Region"  # optional
REQUIRED_HEADERS = [HEADER_API_KEY]

_PLACEHOLDER = re.compile(r"^\$\{.*\}$")

# Per-request isolation: the middleware sets these for the duration of one
# HTTP request and resets them in `finally`. Nothing credential-related is
# ever stored at module level.
_credentials_var: contextvars.ContextVar[KnowBe4Credentials | None] = contextvars.ContextVar("kb4_credentials", default=None)
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("kb4_request_id", default="-")

INSTRUCTIONS = (
    "KnowBe4 runs security awareness training: simulated phishing campaigns "
    "send phishing security tests (PSTs) to users, and training campaigns "
    "enroll users in courses. Users and groups carry a risk score.\n"
    "Usage:\n"
    "- Overview: knowbe4_reporting_risk_overview, _phishing_summary, _training_summary.\n"
    "- Who clicked: knowbe4_phishing_security_tests_list -> "
    "knowbe4_phishing_security_test_recipients(pst_id).\n"
    "- Training status of a person: knowbe4_training_enrollments_list(user_id).\n"
    "- Lists page with page (from 1) and per_page (default 50, max 200).\n"
    "The Reporting API is read-only and limited to about 2,000 calls per day plus "
    "one per licensed user, 4 per second; prefer the summaries over paging "
    "through every record."
)


def get_client_from_context() -> KnowBe4Client | None:
    """The client for the current request, or None outside a request."""
    credentials = _credentials_var.get()
    if credentials is None:
        return None
    return KnowBe4Client(credentials)


def _clean(value: str | None) -> str | None:
    text = (value or "").strip()
    if not text or _PLACEHOLDER.match(text):
        return None
    return text


def normalize_region(value: str | None) -> str | None:
    """'us', 'EU', 'eu.api.knowbe4.com', 'https://ca.knowbe4.com' -> region; default when empty; None when unknown."""
    if not value:
        return DEFAULT_REGION
    text = re.sub(r"^https?://", "", value.strip().lower()).split("/", 1)[0]
    if text in ("training.knowbe4.com", "us.api.knowbe4.com"):
        return "us"
    text = text.removesuffix(".knowbe4.com").removesuffix(".api")
    return text if text in REGION_BASE_URLS else None


def _error(scope: Scope, receive: Receive, send: Send, status: int, error: str, message: str):
    return JSONResponse({"error": error, "message": message, "required_headers": REQUIRED_HEADERS}, status_code=status)(
        scope, receive, send
    )


class GatewayCredentialsMiddleware:
    """Reads the KnowBe4 key and region on /mcp requests into the request context."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope.get("path", "").startswith("/mcp"):
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        api_key = _clean(request.headers.get(HEADER_API_KEY))
        if not api_key:
            await _error(scope, receive, send, 401, "Missing credentials", f"Missing header(s): {HEADER_API_KEY}")
            return
        region = normalize_region(_clean(request.headers.get(HEADER_REGION)))
        if region is None:
            await _error(scope, receive, send, 400, "Invalid credentials", f"{HEADER_REGION} must be one of: {', '.join(REGION_BASE_URLS)}")
            return

        request_id = (request.headers.get("x-request-id") or "").strip()[:64] or uuid.uuid4().hex[:12]
        creds_token = _credentials_var.set(KnowBe4Credentials(api_key, region))
        rid_token = request_id_var.set(request_id)
        try:
            await self.app(scope, receive, send)
        finally:
            _credentials_var.reset(creds_token)
            request_id_var.reset(rid_token)


def create_mcp_server(settings: Settings | None = None) -> FastMCP:
    """Build the FastMCP server and register every tool."""
    mcp = FastMCP(
        name="knowbe4-mcp",
        instructions=INSTRUCTIONS,
        # The service sits behind the gateway, so Host is never localhost;
        # DNS-rebinding protection would reject those requests with 421.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
        stateless_http=True,
    )

    client_factory: Callable[[], KnowBe4Client | None] = get_client_from_context

    from .tools import account, groups, navigation, phishing, reporting, training, users

    for module in (navigation, account, users, groups, phishing, training, reporting):
        module.register(mcp, client_factory)

    return mcp
