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
"""Tool discovery (kept for compatibility: every tool is always listed) and the connection check."""

from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from .._json import compact as to_json
from ..api_client import KnowBe4Client
from ._common import LOCAL, READ_ONLY, ClientFactory, run_tool

DOMAINS: dict[str, tuple[str, list[str]]] = {
    "account": ("Account info and risk score history.", ["knowbe4_account_get", "knowbe4_account_risk_score_history"]),
    "users": ("Users and their risk scores.", ["knowbe4_users_list", "knowbe4_users_get", "knowbe4_users_risk_score_history"]),
    "groups": (
        "Groups, members and group risk scores.",
        ["knowbe4_groups_list", "knowbe4_groups_get", "knowbe4_groups_members", "knowbe4_groups_risk_score_history"],
    ),
    "phishing": (
        "Phishing campaigns, security tests and recipient results.",
        [
            "knowbe4_phishing_campaigns_list",
            "knowbe4_phishing_campaigns_get",
            "knowbe4_phishing_security_tests_list",
            "knowbe4_phishing_campaign_tests",
            "knowbe4_phishing_security_test_get",
            "knowbe4_phishing_security_test_recipients",
            "knowbe4_phishing_security_test_recipient",
        ],
    ),
    "training": (
        "Training campaigns, enrollments, purchased content and policies.",
        [
            "knowbe4_training_campaigns_list",
            "knowbe4_training_campaigns_get",
            "knowbe4_training_enrollments_list",
            "knowbe4_training_enrollments_get",
            "knowbe4_store_purchases_list",
            "knowbe4_store_purchases_get",
            "knowbe4_policies_list",
            "knowbe4_policies_get",
        ],
    ),
    "reporting": (
        "Summaries: phishing results, training progress, risk overview.",
        ["knowbe4_reporting_phishing_summary", "knowbe4_reporting_training_summary", "knowbe4_reporting_risk_overview"],
    ),
}

Domain = Literal["account", "users", "groups", "phishing", "training", "reporting"]


def register(mcp: FastMCP, client_factory: ClientFactory) -> None:
    @mcp.tool(annotations=LOCAL)
    async def knowbe4_navigate(domain: Annotated[Domain, Field(description="Area to describe.")]) -> str:
        """Describe the tools of one KnowBe4 area. All tools are already callable; this changes nothing."""
        summary, tools = DOMAINS[domain]
        return to_json({"domain": domain, "summary": summary, "tools": tools})

    @mcp.tool(annotations=LOCAL)
    async def knowbe4_back() -> str:
        """Kept for compatibility: there is no navigation state, every tool is always available."""
        return to_json({"domains": list(DOMAINS), "message": "All tools are listed; call any of them directly."})

    @mcp.tool(annotations=READ_ONLY)
    async def knowbe4_status() -> str:
        """Check the KnowBe4 connection: region and account name."""

        async def action(client: KnowBe4Client) -> dict:
            account = await client.get("v1/account")
            name = account.get("name") if isinstance(account, dict) else None
            return {"connected": True, "region": client.region, "account": name, "domains": list(DOMAINS)}

        return await run_tool("knowbe4_status", client_factory, action)
