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
"""Summaries computed from the Reporting API: phishing results, training progress, risk overview."""

from collections import Counter
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..api_client import KnowBe4Client
from ..config import MAX_PAGE_SIZE
from ._common import READ_ONLY, ClientFactory, Page, PerPage, all_rows, compact, run_tool

_COUNTS = ("delivered_count", "opened_count", "clicked_count", "replied_count", "attachment_open_count", "data_entered_count", "reported_count", "bounced_count")
_DONE = {"closed", "completed", "complete", "ended"}


async def _rows(client: KnowBe4Client, path: str, page: int | None, per_page: int | None) -> tuple[list, str]:
    """One page when asked for, otherwise every page (up to 2000 records)."""
    if page or per_page:
        rows = await client.get(path, {"page": page or 1, "per_page": per_page or MAX_PAGE_SIZE})
        return (rows if isinstance(rows, list) else []), f"page {page or 1}"
    return await all_rows(client, path), "all"


def _rate(part: int, whole: int) -> float | None:
    return round(part / whole * 100, 2) if whole else None


def register(mcp: FastMCP, client_factory: ClientFactory) -> None:
    @mcp.tool(annotations=READ_ONLY)
    async def knowbe4_reporting_phishing_summary(page: Page = None, per_page: PerPage = None) -> str:
        """Phishing results across security tests: delivered, opened, clicked, reported, rates, phish-prone %.

        Covers every test unless page / per_page is given.
        """

        async def action(client: KnowBe4Client) -> dict:
            tests, scope = await _rows(client, "v1/phishing/security_tests", page, per_page)
            totals = {k: sum(int(t.get(k) or 0) for t in tests if isinstance(t, dict)) for k in _COUNTS}
            prone = [float(t["phish_prone_percentage"]) for t in tests if isinstance(t, dict) and isinstance(t.get("phish_prone_percentage"), (int, float))]
            delivered = totals["delivered_count"]
            return compact(
                {
                    "scope": scope,
                    "security_tests": len(tests),
                    **{f"total_{k.removesuffix('_count')}": v for k, v in totals.items()},
                    "average_phish_prone_percentage": round(sum(prone) / len(prone), 2) if prone else None,
                    "open_rate": _rate(totals["opened_count"], delivered),
                    "click_rate": _rate(totals["clicked_count"], delivered),
                    "report_rate": _rate(totals["reported_count"], delivered),
                }
            )

        return await run_tool("knowbe4_reporting_phishing_summary", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def knowbe4_reporting_training_summary(page: Page = None, per_page: PerPage = None) -> str:
        """Training campaigns by status, with average completion percentage.

        Covers every campaign unless page / per_page is given.
        """

        async def action(client: KnowBe4Client) -> dict:
            campaigns, scope = await _rows(client, "v1/training/campaigns", page, per_page)
            campaigns = [c for c in campaigns if isinstance(c, dict)]
            by_status = Counter(str(c.get("status") or "unknown") for c in campaigns)
            completed = sum(n for s, n in by_status.items() if s.lower() in _DONE)
            pct = [float(c["completion_percentage"]) for c in campaigns if isinstance(c.get("completion_percentage"), (int, float))]
            return compact(
                {
                    "scope": scope,
                    "total_campaigns": len(campaigns),
                    "completed_campaigns": completed,
                    "active_campaigns": len(campaigns) - completed,
                    "by_status": dict(by_status),
                    "average_completion_percentage": round(sum(pct) / len(pct), 2) if pct else None,
                }
            )

        return await run_tool("knowbe4_reporting_training_summary", client_factory, action)

    @mcp.tool(annotations=READ_ONLY)
    async def knowbe4_reporting_risk_overview() -> str:
        """Risk overview: account risk score and its recent history, plus the five highest-risk groups."""

        async def action(client: KnowBe4Client) -> dict:
            account = await client.get("v1/account")
            account = account if isinstance(account, dict) else {}
            history = await client.get("v1/account/risk_score_history", {"page": 1, "per_page": 10})
            groups = [g for g in await all_rows(client, "v1/groups") if isinstance(g, dict)]
            scored = [g for g in groups if isinstance(g.get("current_risk_score"), (int, float))]
            top: list[dict[str, Any]] = [
                compact({"id": g.get("id"), "name": g.get("name"), "risk_score": g.get("current_risk_score"), "member_count": g.get("member_count")})
                for g in sorted(scored, key=lambda g: g["current_risk_score"], reverse=True)[:5]
            ]
            return compact(
                {
                    "account_name": account.get("name"),
                    "current_risk_score": account.get("current_risk_score"),
                    "number_of_seats": account.get("number_of_seats"),
                    "subscription_level": account.get("subscription_level"),
                    "recent_risk_history": history if isinstance(history, list) else [],
                    "highest_risk_groups": top,
                    "groups_scored": len(scored),
                }
            )

        return await run_tool("knowbe4_reporting_risk_overview", client_factory, action)
