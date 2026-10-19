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
"""Account: the KnowBe4 account and its risk score over time."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from ..api_client import KnowBe4Client
from ._common import ClientFactory, FullHistory, Page, PerPage, READ_ONLY, list_page, run_tool


def register(mcp: FastMCP, client_factory: ClientFactory) -> None:
    @mcp.tool(annotations=READ_ONLY)
    async def knowbe4_account_get() -> str:
        """Get the account: name, type, domains, admins, seats, subscription level, current risk score."""

        async def action(client: KnowBe4Client) -> Any:
            return await client.get("v1/account")

        return await run_tool("knowbe4_account_get", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def knowbe4_account_risk_score_history(
        full: FullHistory = None,
        page: Page = None,
        per_page: PerPage = None,
    ) -> str:
        """Get the account's risk score history (date and score)."""

        async def action(client: KnowBe4Client) -> dict:
            return await list_page(client, "v1/account/risk_score_history", "history", {"full": full}, page, per_page)

        return await run_tool("knowbe4_account_risk_score_history", client_factory, action)
