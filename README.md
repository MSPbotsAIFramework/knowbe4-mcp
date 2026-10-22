# KnowBe4 MCP Server

An [MCP](https://modelcontextprotocol.io) server for the [KnowBe4](https://www.knowbe4.com) Reporting API (v1),
the security awareness training platform MSPs use to phish-test and train their clients' users.
It lets an AI agent read the account and risk scores, users and groups, phishing campaigns with
their security tests and per-recipient results, training campaigns and enrollments, purchased
content and policies, and summaries across them. The API is read-only, so every tool is too.

- Transport: MCP Streamable HTTP at `POST /mcp`, health probe at `GET /health`
- Stateless and multi-tenant: credentials arrive on every request as HTTP headers and are
  never stored; every tool is listed from the first `tools/list`
- Python 3.12, [uv](https://docs.astral.sh/uv/), FastMCP, httpx
- License: Apache-2.0, Copyright 2026 MSPbots.ai

## Authentication headers

| Header | Required | Type | Default | Allowed values | Description | Example |
|---|---|---|---|---|---|---|
| `X-KnowBe4-API-Key` | Yes | string | none | - | Reporting API key | `your-api-key` |
| `X-KnowBe4-Region` | No | string | `us` | `us`, `eu`, `ca`, `uk`, `de` (or the region's host) | Server hosting the account | `eu` |

Where to get them: generate the key in the KnowBe4 console's Reporting API management page (User
Event API keys are different and do not work here). The region is the server the console runs on:
`training.knowbe4.com` is `us`, `eu.knowbe4.com` is `eu`, and so on.

How the key is sent: every call goes to `https://{region}.api.knowbe4.com/v1/...` with
`Authorization: Bearer <key>`.

A request to `/mcp` without the key gets HTTP 401; an unknown region does not block the request, and tools return `invalid_argument` instead.

## Tools

All tools return a JSON string. Lists take `page` (from 1) and `per_page` (default 50, max 200) and return
`{count, page, has_more, next_page, offset, next_offset}`. They also take `offset` (record position from 0,
overrides `page`): pass `next_offset` from the previous result to continue. When a page is too large for one
response and is cut, `next_offset` starts right after the last record returned, so no record is skipped
(KnowBe4 pages by number only, and the rest of a cut page is on no other page).

| Area | Tools |
|---|---|
| Overview | `knowbe4_navigate` (**domain**), `knowbe4_back`, `knowbe4_status` |
| Account | `knowbe4_account_get`, `knowbe4_account_risk_score_history` (full) |
| Users | `knowbe4_users_list` (status, group_id, expand_groups), `knowbe4_users_get` (**user_id**), `knowbe4_users_risk_score_history` (**user_id**, full) |
| Groups | `knowbe4_groups_list` (status), `knowbe4_groups_get` (**group_id**), `knowbe4_groups_members` (**group_id**), `knowbe4_groups_risk_score_history` (**group_id**, full) |
| Phishing | `knowbe4_phishing_campaigns_list`, `knowbe4_phishing_campaigns_get` (**campaign_id**), `knowbe4_phishing_security_tests_list`, `knowbe4_phishing_campaign_tests` (**campaign_id**), `knowbe4_phishing_security_test_get` (**pst_id**), `knowbe4_phishing_security_test_recipients` (**pst_id**), `knowbe4_phishing_security_test_recipient` (**pst_id**, **recipient_id**); the test tools take `campaign_type: callback` for callback phishing |
| Training | `knowbe4_training_campaigns_list`, `knowbe4_training_campaigns_get` (**campaign_id**), `knowbe4_training_enrollments_list` (campaign_id, user_id, store_purchase_id, exclude_archived_users), `knowbe4_training_enrollments_get` (**enrollment_id**), `knowbe4_store_purchases_list`, `knowbe4_store_purchases_get` (**purchase_id**), `knowbe4_policies_list`, `knowbe4_policies_get` (**policy_id**) |
| Reporting | `knowbe4_reporting_phishing_summary`, `knowbe4_reporting_training_summary` (every page unless page / per_page is given), `knowbe4_reporting_risk_overview` |

Errors come back as a JSON envelope instead of an exception:

```json
{"error": {"code": "unauthorized", "message": "KnowBe4 returned HTTP 401 for v1/users", "retryable": false}}
```

`code` is one of `not_configured`, `unauthorized`, `not_found`, `invalid_argument`,
`rate_limited`, `upstream_error`. Requests are retried with backoff on 429, 5xx and network
errors. KnowBe4 allows 2,000 calls per day plus one per licensed user, at most 4 per second and
50 per minute in bursts.

## Run locally

```bash
uv sync
uv run python -m knowbe4_mcp          # listens on 0.0.0.0:8080
```

or with Docker:

```bash
docker build --platform linux/amd64 -t knowbe4-mcp:dev .
docker run --rm -p 8080:8080 knowbe4-mcp:dev
```

Configuration (environment variables, all optional): `MCP_HTTP_HOST` (default `0.0.0.0`),
`MCP_HTTP_PORT` (default `8080`), `LOG_LEVEL` (default `INFO`). Credentials are never read
from the environment.

## Testing example

```bash
# list tools
curl -s http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-KnowBe4-API-Key: your-api-key" \
  -H "X-KnowBe4-Region: us" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

# phishing results across all security tests
curl -s http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-KnowBe4-API-Key: your-api-key" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"knowbe4_reporting_phishing_summary","arguments":{}}}'
```

Unit tests (no network access needed):

```bash
uv run pytest
```

## Delivery notes

- **Tool count (30).** Kept as is because the tool names are an existing contract; every earlier
  parameter is still accepted. (The optional "lazy loading" meta-tools of older versions, off by
  default, are not included: every tool is listed directly.)
- **API source.** The official OpenAPI document behind KnowBe4's developer portal
  (`https://developer.knowbe4.com/elvis-swagger.yml`, Reporting API).
- **Routes fixed.** Store purchases are `/v1/training/store_purchases` and policies
  `/v1/training/policies`; older versions called `/v1/store/purchases` and `/v1/policies`.
- **New optional parameters** from the official API: `full` on the risk score histories,
  `expand_groups` on users, `campaign_type: callback` on the phishing tests, and the user /
  campaign / content / archived filters on enrollments.
- **Summaries cover everything by default.** The phishing and training summaries read every page
  (up to 2,000 records) unless `page` / `per_page` is passed; older versions summarised only the
  first page.
- **Paging.** KnowBe4 announced that the `page` parameter will be retired in November 2026 in
  favour of cursor paging; the tools still use `page` today, as the published reference does.
- **Not included**: the user "card" UI resource of older versions (an MCP Apps HTML view); the
  tools return the same data as JSON.

## License

Apache License 2.0 - see [LICENSE](LICENSE) and [NOTICE](NOTICE).
