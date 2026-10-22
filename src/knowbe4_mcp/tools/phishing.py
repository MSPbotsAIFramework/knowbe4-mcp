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
"""Phishing: simulated phishing campaigns, their security tests (PSTs) and per-recipient results."""

from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ..api_client import KnowBe4Client
from ._common import CampaignType, ClientFactory, Offset, Page, PerPage, READ_ONLY, compact, list_page, run_tool


def register(mcp: FastMCP, client_factory: ClientFactory) -> None:
    @mcp.tool(annotations=READ_ONLY)
    async def knowbe4_phishing_campaigns_list(
        page: Page = None,
        per_page: PerPage = None,
        offset: Offset = None,
    ) -> str:
        """List phishing campaigns: name, groups, status, frequency, phish-prone %, last and next run."""

        async def action(client: KnowBe4Client) -> dict:
            return await list_page(client, "v1/phishing/campaigns", "campaigns", {}, page, per_page, offset)

        return await run_tool("knowbe4_phishing_campaigns_list", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def knowbe4_phishing_campaigns_get(
        campaign_id: Annotated[int, Field(description="Phishing campaign id.", ge=1)],
        campaign_type: CampaignType = None,
    ) -> str:
        """Get one phishing campaign with its settings and security tests."""

        async def action(client: KnowBe4Client) -> Any:
            return await client.get(f"v1/phishing/campaigns/{campaign_id}", compact({"campaign_type": campaign_type}))

        return await run_tool("knowbe4_phishing_campaigns_get", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def knowbe4_phishing_security_tests_list(
        campaign_type: CampaignType = None,
        page: Page = None,
        per_page: PerPage = None,
        offset: Offset = None,
    ) -> str:
        """List phishing security tests (PSTs): name, status, dates, delivered / opened / clicked / reported."""

        async def action(client: KnowBe4Client) -> dict:
            return await list_page(client, "v1/phishing/security_tests", "security_tests", {"campaign_type": campaign_type}, page, per_page, offset)

        return await run_tool("knowbe4_phishing_security_tests_list", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def knowbe4_phishing_campaign_tests(
        campaign_id: Annotated[int, Field(description="Phishing campaign id.", ge=1)],
        campaign_type: CampaignType = None,
        page: Page = None,
        per_page: PerPage = None,
        offset: Offset = None,
    ) -> str:
        """List the security tests (PSTs) of one phishing campaign with their result counts."""

        async def action(client: KnowBe4Client) -> dict:
            return await list_page(client, f"v1/phishing/campaigns/{campaign_id}/security_tests", "security_tests", {"campaign_type": campaign_type}, page, per_page, offset)

        return await run_tool("knowbe4_phishing_campaign_tests", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def knowbe4_phishing_security_test_get(
        pst_id: Annotated[int, Field(description="Phishing security test id.", ge=1)],
        campaign_type: CampaignType = None,
    ) -> str:
        """Get one phishing security test: template, landing page, dates and result counts."""

        async def action(client: KnowBe4Client) -> Any:
            return await client.get(f"v1/phishing/security_tests/{pst_id}", compact({"campaign_type": campaign_type}))

        return await run_tool("knowbe4_phishing_security_test_get", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def knowbe4_phishing_security_test_recipients(
        pst_id: Annotated[int, Field(description="Phishing security test id.", ge=1)],
        campaign_type: CampaignType = None,
        page: Page = None,
        per_page: PerPage = None,
        offset: Offset = None,
    ) -> str:
        """List a security test's recipients and what each did (delivered, opened, clicked, reported)."""

        async def action(client: KnowBe4Client) -> dict:
            return await list_page(client, f"v1/phishing/security_tests/{pst_id}/recipients", "recipients", {"campaign_type": campaign_type}, page, per_page, offset)

        return await run_tool("knowbe4_phishing_security_test_recipients", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def knowbe4_phishing_security_test_recipient(
        pst_id: Annotated[int, Field(description="Phishing security test id.", ge=1)],
        recipient_id: Annotated[int, Field(description="Recipient id.", ge=1)],
        campaign_type: CampaignType = None,
    ) -> str:
        """Get one recipient's result in a security test: timestamps, IP, browser, OS."""

        async def action(client: KnowBe4Client) -> Any:
            return await client.get(f"v1/phishing/security_tests/{pst_id}/recipients/{recipient_id}", compact({"campaign_type": campaign_type}))

        return await run_tool("knowbe4_phishing_security_test_recipient", client_factory, action)
