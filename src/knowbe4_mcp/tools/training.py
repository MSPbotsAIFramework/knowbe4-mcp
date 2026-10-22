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
"""Training: training campaigns, enrollments, store purchases (content) and policies."""

from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ..api_client import KnowBe4Client
from ._common import ClientFactory, ExcludeArchived, OptionalId, Offset, Page, PerPage, READ_ONLY, list_page, run_tool


def register(mcp: FastMCP, client_factory: ClientFactory) -> None:
    @mcp.tool(annotations=READ_ONLY)
    async def knowbe4_training_campaigns_list(
        page: Page = None,
        per_page: PerPage = None,
        offset: Offset = None,
    ) -> str:
        """List training campaigns: name, groups, modules, status, completion %, start and end dates."""

        async def action(client: KnowBe4Client) -> dict:
            return await list_page(client, "v1/training/campaigns", "campaigns", {}, page, per_page, offset)

        return await run_tool("knowbe4_training_campaigns_list", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def knowbe4_training_campaigns_get(
        campaign_id: Annotated[int, Field(description="Training campaign id.", ge=1)],
    ) -> str:
        """Get one training campaign with its content, groups and completion percentage."""

        async def action(client: KnowBe4Client) -> Any:
            return await client.get(f"v1/training/campaigns/{campaign_id}")

        return await run_tool("knowbe4_training_campaigns_get", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def knowbe4_training_enrollments_list(
        campaign_id: OptionalId = None,
        user_id: OptionalId = None,
        store_purchase_id: OptionalId = None,
        exclude_archived_users: ExcludeArchived = None,
        page: Page = None,
        per_page: PerPage = None,
        offset: Offset = None,
    ) -> str:
        """List training enrollments: user, module, campaign, status, enrollment / start / completion dates."""

        async def action(client: KnowBe4Client) -> dict:
            return await list_page(client, "v1/training/enrollments", "enrollments", {"campaign_id": campaign_id, "user_id": user_id, "store_purchase_id": store_purchase_id, "exclude_archived_users": exclude_archived_users}, page, per_page, offset)

        return await run_tool("knowbe4_training_enrollments_list", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def knowbe4_training_enrollments_get(
        enrollment_id: Annotated[int, Field(description="Enrollment id.", ge=1)],
    ) -> str:
        """Get one training enrollment: user, module, status, time spent, dates."""

        async def action(client: KnowBe4Client) -> Any:
            return await client.get(f"v1/training/enrollments/{enrollment_id}")

        return await run_tool("knowbe4_training_enrollments_get", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def knowbe4_store_purchases_list(
        page: Page = None,
        per_page: PerPage = None,
        offset: Offset = None,
    ) -> str:
        """List purchased training content: name, type, duration, publisher, purchase date."""

        async def action(client: KnowBe4Client) -> dict:
            return await list_page(client, "v1/training/store_purchases", "store_purchases", {}, page, per_page, offset)

        return await run_tool("knowbe4_store_purchases_list", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def knowbe4_store_purchases_get(
        purchase_id: Annotated[int, Field(description="Store purchase id.", ge=1)],
    ) -> str:
        """Get one purchased training content item."""

        async def action(client: KnowBe4Client) -> Any:
            return await client.get(f"v1/training/store_purchases/{purchase_id}")

        return await run_tool("knowbe4_store_purchases_get", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def knowbe4_policies_list(
        page: Page = None,
        per_page: PerPage = None,
        offset: Offset = None,
    ) -> str:
        """List uploaded policies (documents users must acknowledge): name, status, minimum time."""

        async def action(client: KnowBe4Client) -> dict:
            return await list_page(client, "v1/training/policies", "policies", {}, page, per_page, offset)

        return await run_tool("knowbe4_policies_list", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def knowbe4_policies_get(
        policy_id: Annotated[int, Field(description="Policy id.", ge=1)],
    ) -> str:
        """Get one uploaded policy."""

        async def action(client: KnowBe4Client) -> Any:
            return await client.get(f"v1/training/policies/{policy_id}")

        return await run_tool("knowbe4_policies_get", client_factory, action)
