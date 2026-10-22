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
"""Users: people in the account, their groups and risk scores."""

from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ..api_client import KnowBe4Client
from ._common import ClientFactory, ExpandGroups, FullHistory, GroupFilter, Offset, Page, PerPage, READ_ONLY, UserStatus, list_page, run_tool


def register(mcp: FastMCP, client_factory: ClientFactory) -> None:
    @mcp.tool(annotations=READ_ONLY)
    async def knowbe4_users_list(
        status: UserStatus = None,
        group_id: GroupFilter = None,
        expand_groups: ExpandGroups = None,
        page: Page = None,
        per_page: PerPage = None,
        offset: Offset = None,
    ) -> str:
        """List users: name, email, department, manager, status, phish-prone %, risk score, groups."""

        async def action(client: KnowBe4Client) -> dict:
            return await list_page(client, "v1/users", "users", {"status": status, "group_id": group_id, "expand": "group" if expand_groups else None}, page, per_page, offset)

        return await run_tool("knowbe4_users_list", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def knowbe4_users_get(
        user_id: Annotated[int, Field(description="User id.", ge=1)],
    ) -> str:
        """Get one user: profile, status, phish-prone percentage, current risk score, groups."""

        async def action(client: KnowBe4Client) -> Any:
            return await client.get(f"v1/users/{user_id}")

        return await run_tool("knowbe4_users_get", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def knowbe4_users_risk_score_history(
        user_id: Annotated[int, Field(description="User id.", ge=1)],
        full: FullHistory = None,
        page: Page = None,
        per_page: PerPage = None,
        offset: Offset = None,
    ) -> str:
        """Get one user's risk score history (date and score)."""

        async def action(client: KnowBe4Client) -> dict:
            return await list_page(client, f"v1/users/{user_id}/risk_score_history", "history", {"full": full}, page, per_page, offset)

        return await run_tool("knowbe4_users_risk_score_history", client_factory, action)
