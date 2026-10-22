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
"""Request shapes, paging, retries, summaries and routes against a mocked KnowBe4 API."""

import json

import httpx
import pytest

from knowbe4_mcp import api_client
from knowbe4_mcp.api_client import KnowBe4Client, KnowBe4Credentials, KnowBe4Error
from knowbe4_mcp.server import _credentials_var, create_mcp_server

CREDS = KnowBe4Credentials("key-123", "us")


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    async def instant(_seconds):
        return None

    monkeypatch.setattr(api_client.asyncio, "sleep", instant)


class Recorder:
    """Mock transport: replies by method + path below /v1/."""

    def __init__(self, routes=None, default=None):
        self.requests: list[httpx.Request] = []
        self.routes = routes or {}
        self.default = default if default is not None else []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path.removeprefix("/v1/")
        reply = self.routes.get(f"{request.method} {path}", self.routes.get(path, self.default))
        if callable(reply):
            return reply(request)
        return httpx.Response(200, json=reply)

    def calls(self, path: str) -> list[httpx.Request]:
        return [r for r in self.requests if r.url.path == f"/v1/{path}"]


async def _call(monkeypatch, recorder: Recorder, tool: str, args: dict):
    http = httpx.AsyncClient(transport=httpx.MockTransport(recorder))
    monkeypatch.setattr(api_client, "_get_shared_http_client", lambda: http)
    ctx = _credentials_var.set(CREDS)
    try:
        content, _ = await create_mcp_server().call_tool(tool, args)
    finally:
        _credentials_var.reset(ctx)
    return json.loads(content[0].text)


def _client(recorder: Recorder) -> KnowBe4Client:
    return KnowBe4Client(CREDS, httpx.AsyncClient(transport=httpx.MockTransport(recorder)))


async def test_bearer_key_and_region_host():
    rec = Recorder()
    await _client(rec).get("v1/users", {"page": 1})
    assert rec.requests[0].headers["authorization"] == "Bearer key-123"
    assert str(rec.requests[0].url) == "https://us.api.knowbe4.com/v1/users?page=1"


async def test_get_is_retried_on_429_and_5xx():
    replies = iter([httpx.Response(429, headers={"Retry-After": "1"}), httpx.Response(503), httpx.Response(200, json=[])])
    rec = Recorder({"users": lambda r: next(replies)})
    assert await _client(rec).get("v1/users") == []
    assert len(rec.requests) == 3


async def test_errors_map_to_envelopes(monkeypatch):
    rec = Recorder({"users/9": lambda r: httpx.Response(404, json={"message": "Not found"}), "users": lambda r: httpx.Response(401, json={"message": "Invalid token"})})
    missing = await _call(monkeypatch, rec, "knowbe4_users_get", {"user_id": 9})
    assert missing["error"]["code"] == "not_found"
    denied = await _call(monkeypatch, rec, "knowbe4_users_list", {})
    assert denied["error"]["code"] == "unauthorized" and denied["error"]["message"].endswith("Invalid token")


async def test_users_list_filters_and_paging(monkeypatch):
    rec = Recorder({"users": [{"id": i} for i in range(50)]})
    result = await _call(monkeypatch, rec, "knowbe4_users_list", {"status": "active", "group_id": 4, "expand_groups": True, "page": 2, "per_page": 50})
    params = rec.requests[0].url.params
    assert (params["status"], params["group_id"], params["expand"], params["page"], params["per_page"]) == ("active", "4", "group", "2", "50")
    assert (result["count"], result["has_more"], result["next_page"]) == (50, True, 3)


async def test_short_page_is_the_last(monkeypatch):
    rec = Recorder({"groups": [{"id": 1}]})
    result = await _call(monkeypatch, rec, "knowbe4_groups_list", {})
    assert rec.requests[0].url.params["per_page"] == "50"
    assert result == {"groups": [{"id": 1}], "count": 1, "page": 1, "has_more": False, "offset": 0}


@pytest.mark.parametrize(
    "tool,args,path",
    [
        ("knowbe4_account_get", {}, "account"),
        ("knowbe4_account_risk_score_history", {"full": True}, "account/risk_score_history"),
        ("knowbe4_users_risk_score_history", {"user_id": 5}, "users/5/risk_score_history"),
        ("knowbe4_groups_get", {"group_id": 4}, "groups/4"),
        ("knowbe4_groups_members", {"group_id": 4}, "groups/4/members"),
        ("knowbe4_groups_risk_score_history", {"group_id": 4}, "groups/4/risk_score_history"),
        ("knowbe4_phishing_campaigns_list", {}, "phishing/campaigns"),
        ("knowbe4_phishing_campaigns_get", {"campaign_id": 7}, "phishing/campaigns/7"),
        ("knowbe4_phishing_security_tests_list", {}, "phishing/security_tests"),
        ("knowbe4_phishing_campaign_tests", {"campaign_id": 7}, "phishing/campaigns/7/security_tests"),
        ("knowbe4_phishing_security_test_get", {"pst_id": 8}, "phishing/security_tests/8"),
        ("knowbe4_phishing_security_test_recipients", {"pst_id": 8}, "phishing/security_tests/8/recipients"),
        ("knowbe4_phishing_security_test_recipient", {"pst_id": 8, "recipient_id": 9}, "phishing/security_tests/8/recipients/9"),
        ("knowbe4_training_campaigns_list", {}, "training/campaigns"),
        ("knowbe4_training_campaigns_get", {"campaign_id": 3}, "training/campaigns/3"),
        ("knowbe4_training_enrollments_get", {"enrollment_id": 6}, "training/enrollments/6"),
        ("knowbe4_store_purchases_list", {}, "training/store_purchases"),
        ("knowbe4_store_purchases_get", {"purchase_id": 2}, "training/store_purchases/2"),
        ("knowbe4_policies_list", {}, "training/policies"),
        ("knowbe4_policies_get", {"policy_id": 1}, "training/policies/1"),
    ],
)
async def test_routes(monkeypatch, tool, args, path):
    rec = Recorder()
    await _call(monkeypatch, rec, tool, args)
    assert rec.requests[0].url.path == f"/v1/{path}" and rec.requests[0].method == "GET"


async def test_risk_history_full_flag(monkeypatch):
    rec = Recorder()
    await _call(monkeypatch, rec, "knowbe4_account_risk_score_history", {"full": True})
    assert rec.requests[0].url.params["full"] == "true"


async def test_callback_phishing_flag(monkeypatch):
    rec = Recorder()
    await _call(monkeypatch, rec, "knowbe4_phishing_security_test_get", {"pst_id": 8, "campaign_type": "callback"})
    assert rec.requests[0].url.params["campaign_type"] == "callback"


async def test_enrollment_filters(monkeypatch):
    rec = Recorder()
    await _call(monkeypatch, rec, "knowbe4_training_enrollments_list", {"user_id": 5, "campaign_id": 3, "exclude_archived_users": True})
    params = rec.requests[0].url.params
    assert (params["user_id"], params["campaign_id"], params["exclude_archived_users"]) == ("5", "3", "true")


async def test_phishing_summary_reads_every_page(monkeypatch):
    first = [{"delivered_count": 10, "opened_count": 4, "clicked_count": 2, "reported_count": 1, "phish_prone_percentage": 20.0}] * 200
    second = [{"delivered_count": 10, "opened_count": 0, "clicked_count": 0, "reported_count": 5, "phish_prone_percentage": 0}]

    def tests(request):
        return httpx.Response(200, json=first if request.url.params["page"] == "1" else second)

    rec = Recorder({"phishing/security_tests": tests})
    result = await _call(monkeypatch, rec, "knowbe4_reporting_phishing_summary", {})
    assert len(rec.requests) == 2 and result["scope"] == "all" and result["security_tests"] == 201
    assert (result["total_delivered"], result["total_clicked"], result["total_reported"]) == (2010, 400, 205)
    assert result["click_rate"] == round(400 / 2010 * 100, 2)


async def test_phishing_summary_one_page(monkeypatch):
    rec = Recorder({"phishing/security_tests": [{"delivered_count": 4, "clicked_count": 1}]})
    result = await _call(monkeypatch, rec, "knowbe4_reporting_phishing_summary", {"page": 3})
    assert result["scope"] == "page 3" and rec.requests[0].url.params["page"] == "3" and result["click_rate"] == 25.0


async def test_training_summary(monkeypatch):
    campaigns = [{"status": "Closed", "completion_percentage": 100}, {"status": "In Progress", "completion_percentage": 40}, {"status": "Completed"}]
    rec = Recorder({"training/campaigns": campaigns})
    result = await _call(monkeypatch, rec, "knowbe4_reporting_training_summary", {})
    assert (result["total_campaigns"], result["completed_campaigns"], result["active_campaigns"]) == (3, 2, 1)
    assert result["by_status"] == {"Closed": 1, "In Progress": 1, "Completed": 1} and result["average_completion_percentage"] == 70.0


async def test_risk_overview(monkeypatch):
    groups = [{"id": i, "name": f"G{i}", "current_risk_score": i * 10, "member_count": i} for i in range(1, 8)] + [{"id": 99, "name": "none"}]
    rec = Recorder(
        {
            "account": {"name": "Example Co", "current_risk_score": 33.5, "number_of_seats": 120, "subscription_level": "Diamond"},
            "account/risk_score_history": [{"risk_score": 30, "date": "2026-09-01"}],
            "groups": groups,
        }
    )
    result = await _call(monkeypatch, rec, "knowbe4_reporting_risk_overview", {})
    assert result["account_name"] == "Example Co" and result["current_risk_score"] == 33.5
    assert [g["id"] for g in result["highest_risk_groups"]] == [7, 6, 5, 4, 3] and result["groups_scored"] == 7


async def test_status(monkeypatch):
    result = await _call(monkeypatch, Recorder({"account": {"name": "Example Co"}}), "knowbe4_status", {})
    assert result["connected"] is True and result["account"] == "Example Co" and result["region"] == "us"


async def test_non_json_error_body():
    rec = Recorder({"users": lambda r: httpx.Response(400, text="per_page must be at most 500")})
    with pytest.raises(KnowBe4Error) as e:
        await _client(rec).get("v1/users")
    assert "per_page must be at most 500" in e.value.message


# --- Page-number paging that survives truncation -------------------------------------------

# (tool, required args, path, list key) for every tool that pages by number.
PAGED = [
    ("knowbe4_account_risk_score_history", {}, "account/risk_score_history", "history"),
    ("knowbe4_users_list", {}, "users", "users"),
    ("knowbe4_users_risk_score_history", {"user_id": 5}, "users/5/risk_score_history", "history"),
    ("knowbe4_groups_list", {}, "groups", "groups"),
    ("knowbe4_groups_members", {"group_id": 4}, "groups/4/members", "members"),
    ("knowbe4_groups_risk_score_history", {"group_id": 4}, "groups/4/risk_score_history", "history"),
    ("knowbe4_phishing_campaigns_list", {}, "phishing/campaigns", "campaigns"),
    ("knowbe4_phishing_security_tests_list", {}, "phishing/security_tests", "security_tests"),
    ("knowbe4_phishing_campaign_tests", {"campaign_id": 7}, "phishing/campaigns/7/security_tests", "security_tests"),
    ("knowbe4_phishing_security_test_recipients", {"pst_id": 8}, "phishing/security_tests/8/recipients", "recipients"),
    ("knowbe4_training_campaigns_list", {}, "training/campaigns", "campaigns"),
    ("knowbe4_training_enrollments_list", {}, "training/enrollments", "enrollments"),
    ("knowbe4_store_purchases_list", {}, "training/store_purchases", "store_purchases"),
    ("knowbe4_policies_list", {}, "training/policies", "policies"),
]
TOTAL = 47


def _record(i: int, big: bool) -> dict:
    # Many short fields: shortening long values cannot make a big page fit, so it gets cut.
    return {"id": i} | ({f"f{k}": f"{i}-{k}-" + "x" * 60 for k in range(40)} if big else {})


def _paged(path: str, big: bool = True) -> Recorder:
    """A fake API that pages by page number + per_page like KnowBe4 (JSON array replies)."""
    data = [_record(i, big) for i in range(TOTAL)]

    def reply(request: httpx.Request) -> httpx.Response:
        page, size = int(request.url.params["page"]), int(request.url.params["per_page"])
        return httpx.Response(200, json=data[(page - 1) * size : page * size])

    return Recorder({path: reply})


async def _walk(monkeypatch, rec, tool, args, key, first: dict) -> list[int]:
    ids: list[int] = []
    result = await _call(monkeypatch, rec, tool, args | first)
    for _ in range(100):
        assert "retry_page_size" not in result
        ids += [r["id"] for r in result[key]]
        if result.get("next_offset") is None:
            return ids
        result = await _call(monkeypatch, rec, tool, args | {"per_page": 10, "offset": result["next_offset"]})
    raise AssertionError("did not finish")


@pytest.mark.parametrize("tool,args,path,key", PAGED)
async def test_cut_pages_walked_by_next_offset_return_every_record_once(monkeypatch, tool, args, path, key):
    rec = _paged(path)
    first = await _call(monkeypatch, rec, tool, args | {"per_page": 10})
    assert first["truncated"] is True and first["count"] < 10 and "retry_page_size" not in first
    ids = await _walk(monkeypatch, rec, tool, args, key, {"per_page": 10})
    assert ids == list(range(TOTAL))


@pytest.mark.parametrize("tool,args,path,key", PAGED)
async def test_cut_pages_from_a_later_page(monkeypatch, tool, args, path, key):
    ids = await _walk(monkeypatch, _paged(path), tool, args, key, {"page": 3, "per_page": 10})
    assert ids == list(range(20, TOTAL))


@pytest.mark.parametrize("tool,args,path,key", PAGED)
@pytest.mark.parametrize("offset,page,first_id", [(13, "2", 13), (20, "3", 20), (0, "1", 0)])
async def test_offset_reads_the_page_that_holds_it(monkeypatch, tool, args, path, key, offset, page, first_id):
    rec = _paged(path, big=False)
    result = await _call(monkeypatch, rec, tool, args | {"per_page": 10, "offset": offset})
    assert (rec.requests[0].url.params["page"], rec.requests[0].url.params["per_page"]) == (page, "10")
    assert [r["id"] for r in result[key]] == list(range(first_id, int(page) * 10))
    assert (result["offset"], result["next_offset"], result["has_more"]) == (offset, int(page) * 10, True)


@pytest.mark.parametrize("tool,args,path,key", PAGED)
async def test_offset_past_the_end(monkeypatch, tool, args, path, key):
    result = await _call(monkeypatch, _paged(path, big=False), tool, args | {"per_page": 10, "offset": 500})
    assert result[key] == [] and result["has_more"] is False and "next_offset" not in result


@pytest.mark.parametrize("tool,args,path,key", PAGED)
async def test_offset_wins_over_page(monkeypatch, tool, args, path, key):
    rec = _paged(path, big=False)
    result = await _call(monkeypatch, rec, tool, args | {"page": 4, "per_page": 10, "offset": 5})
    assert rec.requests[0].url.params["page"] == "1" and [r["id"] for r in result[key]] == list(range(5, 10))


@pytest.mark.parametrize("tool,args,path,key", PAGED)
async def test_offset_with_default_page_size(monkeypatch, tool, args, path, key):
    rec = _paged(path, big=False)
    result = await _call(monkeypatch, rec, tool, args | {"offset": 3})
    assert (rec.requests[0].url.params["page"], rec.requests[0].url.params["per_page"]) == ("1", "50")
    assert [r["id"] for r in result[key]] == list(range(3, TOTAL)) and result["has_more"] is False


@pytest.mark.parametrize("tool,args,path,key", PAGED)
async def test_page_only_call_is_unchanged(monkeypatch, tool, args, path, key):
    rec = _paged(path, big=False)
    result = await _call(monkeypatch, rec, tool, args | {"page": 2, "per_page": 10})
    assert len(rec.requests) == 1 and dict(rec.requests[0].url.params) == {"page": "2", "per_page": "10"}
    assert [r["id"] for r in result[key]] == list(range(10, 20))
    assert (result["count"], result["page"], result["has_more"], result["next_page"]) == (10, 2, True, 3)
