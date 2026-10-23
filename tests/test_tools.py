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
"""tools/list snapshot, annotations and error-envelope mapping. No network access."""

import asyncio
import json

import pytest

from knowbe4_mcp.api_client import KnowBe4Error
from knowbe4_mcp.server import INSTRUCTIONS, create_mcp_server
from knowbe4_mcp.tools.navigation import DOMAINS

P = {"page", "per_page"}

# Tool name -> (parameters the earlier version declared, required parameters).
# Names and these parameters are a public contract.
EXPECTED: dict[str, tuple[set[str], set[str]]] = {
    "knowbe4_navigate": ({"domain"}, {"domain"}),
    "knowbe4_back": (set(), set()),
    "knowbe4_status": (set(), set()),
    "knowbe4_account_get": (set(), set()),
    "knowbe4_account_risk_score_history": (P, set()),
    "knowbe4_users_list": ({"status", "group_id"} | P, set()),
    "knowbe4_users_get": ({"user_id"}, {"user_id"}),
    "knowbe4_users_risk_score_history": ({"user_id"} | P, {"user_id"}),
    "knowbe4_groups_list": (P, set()),
    "knowbe4_groups_get": ({"group_id"}, {"group_id"}),
    "knowbe4_groups_members": ({"group_id"} | P, {"group_id"}),
    "knowbe4_groups_risk_score_history": ({"group_id"} | P, {"group_id"}),
    "knowbe4_phishing_campaigns_list": (P, set()),
    "knowbe4_phishing_campaigns_get": ({"campaign_id"}, {"campaign_id"}),
    "knowbe4_phishing_security_tests_list": (P, set()),
    "knowbe4_phishing_campaign_tests": ({"campaign_id"} | P, {"campaign_id"}),
    "knowbe4_phishing_security_test_get": ({"pst_id"}, {"pst_id"}),
    "knowbe4_phishing_security_test_recipients": ({"pst_id"} | P, {"pst_id"}),
    "knowbe4_phishing_security_test_recipient": ({"pst_id", "recipient_id"}, {"pst_id", "recipient_id"}),
    "knowbe4_reporting_phishing_summary": (P, set()),
    "knowbe4_reporting_training_summary": (P, set()),
    "knowbe4_reporting_risk_overview": (set(), set()),
    "knowbe4_training_campaigns_list": (P, set()),
    "knowbe4_training_campaigns_get": ({"campaign_id"}, {"campaign_id"}),
    "knowbe4_training_enrollments_list": (P, set()),
    "knowbe4_training_enrollments_get": ({"enrollment_id"}, {"enrollment_id"}),
    "knowbe4_store_purchases_list": (P, set()),
    "knowbe4_store_purchases_get": ({"purchase_id"}, {"purchase_id"}),
    "knowbe4_policies_list": (P, set()),
    "knowbe4_policies_get": ({"policy_id"}, {"policy_id"}),
}


@pytest.fixture(scope="module")
def tools():
    return {t.name: t for t in asyncio.run(create_mcp_server().list_tools())}


def test_tool_names_are_stable(tools):
    assert set(tools) == set(EXPECTED)
    assert len(tools) == 30


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_params(tools, name):
    schema = tools[name].inputSchema
    params, required = EXPECTED[name]
    assert params <= set(schema["properties"])
    assert set(schema.get("required", [])) == required


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_description_budget(tools, name):
    description = (tools[name].description or "").strip()
    assert description, f"{name} has no description"
    assert len(description) <= 500
    assert len(description.splitlines()[0]) <= 100


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_every_tool_is_read_only(tools, name):
    annotations = tools[name].annotations
    assert annotations is not None and annotations.readOnlyHint is True and not annotations.destructiveHint
    assert (annotations.openWorldHint is False) is (name in {"knowbe4_navigate", "knowbe4_back"})


def test_per_page_is_capped(tools):
    paged = [t for t in tools.values() if "per_page" in t.inputSchema["properties"]]
    assert len(paged) == 16
    for tool in paged:
        assert tool.inputSchema["properties"]["per_page"]["anyOf"][0]["maximum"] == 200, tool.name
    content, _ = asyncio.run(create_mcp_server().call_tool("knowbe4_users_list", {"per_page": 201}))
    error = json.loads(content[0].text)["error"]
    assert error["code"] == "invalid_argument" and "less than or equal to 200" in error["message"]


def test_navigate_lists_every_tool():
    listed = {tool for _, names in DOMAINS.values() for tool in names}
    assert listed | {"knowbe4_navigate", "knowbe4_back", "knowbe4_status"} == set(EXPECTED)


def test_instructions_budget():
    assert len(INSTRUCTIONS) <= 1500
    assert "\n" in INSTRUCTIONS


@pytest.mark.parametrize(
    "status,code,retryable",
    [
        (401, "unauthorized", False),
        (403, "unauthorized", False),
        (404, "not_found", False),
        (400, "invalid_argument", False),
        (429, "rate_limited", True),
        (500, "upstream_error", True),
        (0, "upstream_error", True),
    ],
)
def test_error_envelope(status, code, retryable):
    envelope = json.loads(KnowBe4Error(status, "boom").to_envelope())
    assert envelope == {"error": {"code": code, "message": "boom", "retryable": retryable}}


def test_tool_without_credentials_returns_not_configured():
    content, _ = asyncio.run(create_mcp_server().call_tool("knowbe4_users_list", {}))
    assert json.loads(content[0].text)["error"]["code"] == "not_configured"
