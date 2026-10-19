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
"""Groups: user groups, their members and risk scores."""

from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ..api_client import KnowBe4Client
from ._common import ClientFactory, FullHistory, GroupStatus, Page, PerPage, READ_ONLY, list_page, run_tool


def register(mcp: FastMCP, client_factory: ClientFactory) -> None:
    @mcp.tool(annotations=READ_ONLY)
    async def knowbe4_groups_list(
        status: GroupStatus = None,
        page: Page = None,
        per_page: PerPage = None,
    ) -> str:
        """List groups: name, type (console / smart / AD), member count, status, current risk score."""

        async def action(client: KnowBe4Client) -> dict:
            return await list_page(client, "v1/groups", "groups", {"status": status}, page, per_page)

        return await run_tool("knowbe4_groups_list", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def knowbe4_groups_get(
        group_id: Annotated[int, Field(description="Group id.", ge=1)],
    ) -> str:
        """Get one group: name, type, member count, status, current risk score."""

        async def action(client: KnowBe4Client) -> Any:
            return await client.get(f"v1/groups/{group_id}")

        return await run_tool("knowbe4_groups_get", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def knowbe4_groups_members(
        group_id: Annotated[int, Field(description="Group id.", ge=1)],
        page: Page = None,
        per_page: PerPage = None,
    ) -> str:
        """List the users in a group."""

        async def action(client: KnowBe4Client) -> dict:
            return await list_page(client, f"v1/groups/{group_id}/members", "members", {}, page, per_page)

        return await run_tool("knowbe4_groups_members", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def knowbe4_groups_risk_score_history(
        group_id: Annotated[int, Field(description="Group id.", ge=1)],
        full: FullHistory = None,
        page: Page = None,
        per_page: PerPage = None,
    ) -> str:
        """Get one group's risk score history (date and score)."""

        async def action(client: KnowBe4Client) -> dict:
            return await list_page(client, f"v1/groups/{group_id}/risk_score_history", "history", {"full": full}, page, per_page)

        return await run_tool("knowbe4_groups_risk_score_history", client_factory, action)
