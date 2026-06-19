# AISec Digital Risk Monitoring API Documentation

> Frontend handoff for building the UI against the AISec Digital Risk Monitoring backend.

## Base URL

```
http://<EC2_PUBLIC_IP>/aisec-digital-risk
```

## Authentication

All endpoints are **open** — no authentication is required. There are no login, registration, or token flows.

---

## Contents

- [API Endpoints Summary](#api-endpoints-summary)
- [Interactive Docs](#interactive-docs)
- [Enums Reference](#enums-reference)
- [Health Check](#1-health-check)
- [Targets](#2-targets)
- [Scans](#3-scans)
- [Results](#4-results)
- [Complete Workflow Example](#complete-workflow-example)
- [Error Response Format](#error-response-format)
- [Common HTTP Status Codes](#common-http-status-codes)
- [Notes](#notes)

---

## API Endpoints Summary

| Category | Method | Endpoint | Description |
|---|---:|---|---|
| Health | GET | `/health` | Health check |
| Targets | POST | `/api/v1/targets/` | Create or match a target |
| Targets | GET | `/api/v1/targets/` | List all targets |
| Targets | GET | `/api/v1/targets/{target_id}` | Get target details |
| Targets | PUT | `/api/v1/targets/{target_id}` | Update a target |
| Targets | DELETE | `/api/v1/targets/{target_id}` | Soft-delete a target |
| Scans | POST | `/api/v1/scans/` | Create a new scan |
| Scans | GET | `/api/v1/scans/` | List all scans |
| Scans | GET | `/api/v1/scans/scheduled` | List active scheduled scans |
| Scans | GET | `/api/v1/scans/{scan_id}` | Get scan details |
| Scans | DELETE | `/api/v1/scans/{scan_id}/schedule` | Cancel a scheduled scan |
| Results | GET | `/api/v1/results/target/{target_id}` | Get all articles for a target |
| Results | GET | `/api/v1/results/scan/{scan_id}` | Get articles for a specific scan |

---

## Interactive Docs

Swagger UI is available at:

```
http://<EC2_PUBLIC_IP>/aisec-digital-risk/docs
```

---

## Enums Reference

### TargetType

```
"person" | "company" | "team" | "brand" | "organization" | "product" | "other"
```

### ScanType

```
"one_time" | "scheduled"
```

### ScanStatus

```
"pending" | "running" | "completed" | "failed"
```

### ScanDepth

| Value | Queries | Max candidate URLs |
|---|---:|---:|
| `"quick"` | 5 | ~750 |
| `"standard"` | 10 | ~1500 |
| `"thorough"` | 16 | ~2400 |
| `"exhaustive"` | 22 | ~3300 |

> Candidate URLs are collected from Whoogle search (up to 15 pages x 10 results per query).
> After global deduplication, date filtering, and relevance filtering the final scraped count will be lower.

### SentimentType

```
"positive" | "negative" | "neutral"
```

### SecuritySeverity

```
"critical" | "high" | "medium" | "low" | "none"
```

---

# 1. Health Check

## GET `/health`

Checks application health and database connectivity.

**Auth Required:** No  
**Params:** None

### Returns

| Field | Type | Description |
|---|---|---|
| `status` | `str` | `"healthy"` or `"unhealthy"` |
| `version` | `str` | API version (e.g. `"1.0.0"`) |
| `environment` | `str` | Deployment environment (e.g. `"production"`) |
| `database` | `str` | `"connected"` or `"disconnected"` |

### Response Codes

- `200` — Application is healthy
- `503` — Application is unhealthy (database disconnected)

### Example Request

```bash
curl http://<HOST>/aisec-digital-risk/health
```

### Example Response `200`

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "production",
  "database": "connected"
}
```

---

# 2. Targets

Targets are the entities you want to monitor — people, companies, brands, or organizations.

The system uses a two-stage deduplication pipeline when creating targets:

1. **Normalization match** — Fast exact match on a normalized version of the name (lowercased, accent-stripped, punctuation-removed).
2. **LLM match** — If no normalization match is found, AI looks for semantically similar targets (e.g. `Apple` matches `Apple Inc`, `MSFT` matches `Microsoft`).

If a match is found at either stage, the existing target is returned instead of creating a duplicate.  
Articles discovered for a target are shared across all scans.

---

## POST `/api/v1/targets/`

Creates a new monitoring target or returns an existing matched one.

**Auth Required:** No

### Request Body

| Field | Type | Required | Default | Description |
|---|---|:---:|---|---|
| `name` | `str (1-255 chars)` | YES | — | Target name (person, company, etc.) |
| `target_type` | `str` | NO | `"person"` | One of: `person`, `company`, `team`, `brand`, `organization`, `product`, `other` |
| `description` | `str (max 2000 chars) or null` | NO | `null` | Optional context about the target |

### Returns TargetCreateResponse

| Field | Type | Description |
|---|---|---|
| `success` | `bool` | `true` |
| `message` | `str` | Human-readable result message |
| `target` | `TargetResponse` | Created or matched target object |
| `is_new` | `bool` | `true` if a new target was created; `false` if matched to an existing one |
| `matched_by` | `str or null` | How the match was made: `"normalization"`, `"llm"`, or `null` (new target) |
| `match_confidence` | `float or null` | LLM match confidence (0.0-1.0), only present when `matched_by = "llm"` |
| `match_reasoning` | `str or null` | LLM reasoning for the match, only present when `matched_by = "llm"` |

### TargetResponse Fields

| Field | Type | Description |
|---|---|---|
| `id` | `UUID` | Target unique ID |
| `display_name` | `str` | Original user-provided name |
| `normalized_name` | `str` | Canonical deduplication key |
| `target_type` | `str` | Target category |
| `description` | `str or null` | User-provided context |
| `is_active` | `bool` | Whether the target is active |
| `created_at` | `datetime` | Creation timestamp |
| `updated_at` | `datetime` | Last update timestamp |

### Response Codes

- `201` — Target created or matched successfully
- `422` — Validation error

### Example Request

```bash
curl -X POST http://<HOST>/aisec-digital-risk/api/v1/targets/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Apple Inc",
    "target_type": "company",
    "description": "Technology company, maker of iPhone and Mac"
  }'
```

### Example Response `201` — New Target

```json
{
  "success": true,
  "message": "New target 'Apple Inc' created successfully",
  "target": {
    "id": "c3d4e5f6-a7b8-9012-cdef-234567890abc",
    "display_name": "Apple Inc",
    "normalized_name": "apple inc",
    "target_type": "company",
    "description": "Technology company, maker of iPhone and Mac",
    "is_active": true,
    "created_at": "2024-06-15T11:00:00Z",
    "updated_at": "2024-06-15T11:00:00Z"
  },
  "is_new": true,
  "matched_by": null,
  "match_confidence": null,
  "match_reasoning": null
}
```

### Example Response `201` — LLM Matched to Existing Target

```json
{
  "success": true,
  "message": "Target 'Apple' matched to existing target 'Apple Inc' via AI matching (confidence: 95%).",
  "target": {
    "id": "c3d4e5f6-a7b8-9012-cdef-234567890abc",
    "display_name": "Apple Inc",
    "normalized_name": "apple inc",
    "target_type": "company",
    "description": "Technology company, maker of iPhone and Mac",
    "is_active": true,
    "created_at": "2024-06-15T11:00:00Z",
    "updated_at": "2024-06-15T11:00:00Z"
  },
  "is_new": false,
  "matched_by": "llm",
  "match_confidence": 0.95,
  "match_reasoning": "Apple is a commonly used short name for Apple Inc, the technology company."
}
```

---

## GET `/api/v1/targets/`

Lists all active targets with pagination.

**Auth Required:** No

### Query Params

| Param | Type | Default | Description |
|---|---|---:|---|
| `limit` | `int (1-200)` | `50` | Max targets to return |
| `offset` | `int (>=0)` | `0` | Number of targets to skip |

### Returns TargetListResponse

| Field | Type | Description |
|---|---|---|
| `success` | `bool` | `true` |
| `total` | `int` | Total number of active targets |
| `targets` | `TargetResponse[]` | Array of target objects |

### Example Request

```bash
curl "http://<HOST>/aisec-digital-risk/api/v1/targets/?limit=20&offset=0"
```

### Example Response `200`

```json
{
  "success": true,
  "total": 2,
  "targets": [
    {
      "id": "c3d4e5f6-...",
      "display_name": "Apple Inc",
      "normalized_name": "apple inc",
      "target_type": "company",
      "description": "Technology company",
      "is_active": true,
      "created_at": "2024-06-15T11:00:00Z",
      "updated_at": "2024-06-15T11:00:00Z"
    },
    {
      "id": "d4e5f6a7-...",
      "display_name": "Elon Musk",
      "normalized_name": "elon musk",
      "target_type": "person",
      "description": null,
      "is_active": true,
      "created_at": "2024-06-16T09:00:00Z",
      "updated_at": "2024-06-16T09:00:00Z"
    }
  ]
}
```

---

## GET `/api/v1/targets/{target_id}`

Returns details for a specific target by UUID.

**Auth Required:** No

### Path Params

| Param | Type | Description |
|---|---|---|
| `target_id` | `UUID` | Target ID |

### Returns

TargetResponse

### Response Codes

- `200` — Success
- `404` — Target not found

### Example Request

```bash
curl http://<HOST>/aisec-digital-risk/api/v1/targets/c3d4e5f6-a7b8-9012-cdef-234567890abc
```

---

## PUT `/api/v1/targets/{target_id}`

Updates a target's details. If the display name changes, the normalized name is recomputed automatically.

**Auth Required:** No

### Path Params

| Param | Type | Description |
|---|---|---|
| `target_id` | `UUID` | Target ID |

### Request Body

All fields are optional. Only provided fields are updated.

| Field | Type | Required | Description |
|---|---|:---:|---|
| `display_name` | `str or null` | NO | New display name |
| `target_type` | `str or null` | NO | New target type |
| `description` | `str or null` | NO | New description |
| `is_active` | `bool or null` | NO | Activate or deactivate |

### Returns

Updated TargetResponse

### Response Codes

- `200` — Updated successfully
- `404` — Target not found
- `409` — Normalized name already exists

### Example Request

```bash
curl -X PUT http://<HOST>/aisec-digital-risk/api/v1/targets/c3d4e5f6-... \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Updated description for Apple Inc",
    "is_active": true
  }'
```

---

## DELETE `/api/v1/targets/{target_id}`

Soft-deletes a target by setting `is_active` to `false`. Historical data is preserved.

**Auth Required:** No

### Path Params

| Param | Type | Description |
|---|---|---|
| `target_id` | `UUID` | Target ID |

### Returns MessageResponse

| Field | Type | Description |
|---|---|---|
| `success` | `bool` | `true` |
| `message` | `str` | Confirmation message |

### Response Codes

- `200` — Target deactivated
- `404` — Target not found

### Example Request

```bash
curl -X DELETE http://<HOST>/aisec-digital-risk/api/v1/targets/c3d4e5f6-...
```

### Example Response `200`

```json
{
  "success": true,
  "message": "Target 'Apple Inc' has been deactivated"
}
```

---

# 3. Scans

Scans are the core operation of the system. They search the web for content about a target using Whoogle
(a self-hosted Google proxy), scrape discovered pages using Crawl4AI, and run LLM-powered analysis
for sentiment, risk, and security.

## Scan Types

- `one_time` — Executes immediately in the background. Results are stored in the database once complete.
- `scheduled` — First execution runs immediately, then repeats automatically at the specified interval.

## Scan Lifecycle

```
pending -> running -> completed | failed
```

> **Important:** The API returns immediately after creating a scan. Scraping and analysis happen
> asynchronously. Poll `GET /api/v1/scans/{scan_id}` to track progress, then fetch results once
> `status = "completed"`.

## How Discovery Works

Each scan runs multiple Whoogle search queries for the target, paginating each query up to 15 pages
(150 results per query). Results are deduplicated at three levels:

1. **Within each query** — duplicate URLs across pages of the same query are dropped.
2. **Across all queries** — a global dedup set prevents the same URL appearing from two different queries.
3. **Database level** — normalized URLs are checked against existing articles so already-analyzed
   content is never re-scraped or re-analyzed (smart caching).

---

## POST `/api/v1/scans/`

Creates and queues a new scan for a target.

**Auth Required:** No

### Request Body

| Field | Type | Required | Default | Description |
|---|---|:---:|---|---|
| `target_id` | `UUID` | YES | — | UUID of the target to scan |
| `scan_type` | `str` | YES | — | `"one_time"` or `"scheduled"` |
| `scan_depth` | `str` | NO | `"standard"` | `"quick"`, `"standard"`, `"thorough"`, `"exhaustive"` |
| `timeframe` | `str` | NO | `"24 hours"` | How far back to search (e.g. `"24 hours"`, `"1 week"`, `"1 month"`) |
| `schedule_interval` | `str or null` | NO | `null` | Required when `scan_type = "scheduled"` (e.g. `"6 hours"`, `"1 day"`, `"1 week"`) |

### Returns ScanResponse

| Field | Type | Description |
|---|---|---|
| `id` | `UUID` | Scan unique ID |
| `target_id` | `UUID` | Target being scanned |
| `scan_type` | `str` | `"one_time"` or `"scheduled"` |
| `scan_depth` | `str` | Scan depth level |
| `timeframe` | `str` | Search timeframe |
| `schedule_interval` | `str or null` | Recurrence interval |
| `is_schedule_active` | `bool` | Whether the scheduled scan is active |
| `parent_scan_id` | `UUID or null` | Parent scan for scheduled child executions |
| `next_run_at` | `datetime or null` | Next scheduled execution time |
| `status` | `str` | `"pending"`, `"running"`, `"completed"`, or `"failed"` |
| `started_at` | `datetime or null` | When execution began |
| `completed_at` | `datetime or null` | When execution finished |
| `processing_time_sec` | `float or null` | Total execution time in seconds |
| `total_results` | `int` | Total articles found |
| `new_articles_found` | `int` | Articles not previously in the database |
| `positive_count` | `int` | Articles with positive sentiment |
| `negative_count` | `int` | Articles with negative sentiment |
| `neutral_count` | `int` | Articles with neutral sentiment |
| `positive_pct` | `float` | Percentage positive |
| `negative_pct` | `float` | Percentage negative |
| `neutral_pct` | `float` | Percentage neutral |
| `overall_sentiment` | `str or null` | Dominant sentiment |
| `risk_summary` | `list or null` | List of risk flags found |
| `security_alerts` | `list or null` | Security-related findings |
| `platform_breakdown` | `dict or null` | Article count per platform |
| `input_tokens` | `int` | Total LLM input tokens consumed |
| `output_tokens` | `int` | Total LLM output tokens consumed |
| `cost_usd` | `float` | Estimated LLM cost in USD |
| `error_message` | `str or null` | Error details if status is `"failed"` |
| `retry_count` | `int` | Number of retry attempts |
| `created_at` | `datetime` | Scan creation timestamp |

### Response Codes

- `201` — Scan created and queued
- `404` — Target not found
- `422` — Validation error (e.g. missing `schedule_interval` for scheduled scan)

### Example Request — One-Time Scan

```bash
curl -X POST http://<HOST>/aisec-digital-risk/api/v1/scans/ \
  -H "Content-Type: application/json" \
  -d '{
    "target_id": "c3d4e5f6-a7b8-9012-cdef-234567890abc",
    "scan_type": "one_time",
    "scan_depth": "standard",
    "timeframe": "24 hours"
  }'
```

### Example Request — Scheduled Scan

```bash
curl -X POST http://<HOST>/aisec-digital-risk/api/v1/scans/ \
  -H "Content-Type: application/json" \
  -d '{
    "target_id": "c3d4e5f6-a7b8-9012-cdef-234567890abc",
    "scan_type": "scheduled",
    "scan_depth": "thorough",
    "timeframe": "1 week",
    "schedule_interval": "12 hours"
  }'
```

### Example Response `201`

```json
{
  "id": "e5f6a7b8-c9d0-1234-ef56-789012345678",
  "target_id": "c3d4e5f6-...",
  "scan_type": "one_time",
  "scan_depth": "standard",
  "timeframe": "24 hours",
  "schedule_interval": null,
  "is_schedule_active": false,
  "parent_scan_id": null,
  "next_run_at": null,
  "status": "pending",
  "started_at": null,
  "completed_at": null,
  "processing_time_sec": null,
  "total_results": 0,
  "new_articles_found": 0,
  "positive_count": 0,
  "negative_count": 0,
  "neutral_count": 0,
  "positive_pct": 0.0,
  "negative_pct": 0.0,
  "neutral_pct": 0.0,
  "overall_sentiment": null,
  "risk_summary": null,
  "security_alerts": null,
  "platform_breakdown": null,
  "input_tokens": 0,
  "output_tokens": 0,
  "cost_usd": 0.0,
  "error_message": null,
  "retry_count": 0,
  "created_at": "2024-06-15T11:30:00Z"
}
```

---

## GET `/api/v1/scans/`

Lists all scans with optional filters.

**Auth Required:** No

### Query Params

| Param | Type | Default | Description |
|---|---|---:|---|
| `status` | `str or null` | `null` | Filter by status: `"pending"`, `"running"`, `"completed"`, `"failed"` |
| `scan_type` | `str or null` | `null` | Filter by type: `"one_time"`, `"scheduled"` |
| `target_id` | `UUID or null` | `null` | Filter by target |
| `limit` | `int (1-200)` | `50` | Max scans to return |
| `offset` | `int (>=0)` | `0` | Number of scans to skip |

### Returns ScanListResponse

| Field | Type | Description |
|---|---|---|
| `success` | `bool` | `true` |
| `total` | `int` | Total matching scans |
| `scans` | `ScanResponse[]` | Array of scan objects |

### Example Request

```bash
curl "http://<HOST>/aisec-digital-risk/api/v1/scans/?status=completed&limit=10"
```

---

## GET `/api/v1/scans/scheduled`

Lists all active scheduled scans.

**Auth Required:** No

### Query Params

| Param | Type | Default | Description |
|---|---|---:|---|
| `limit` | `int (1-200)` | `50` | Max scans to return |
| `offset` | `int (>=0)` | `0` | Number of scans to skip |

### Returns

ScanListResponse

### Example Request

```bash
curl "http://<HOST>/aisec-digital-risk/api/v1/scans/scheduled"
```

---

## GET `/api/v1/scans/{scan_id}`

Returns detailed information about a specific scan.

**Auth Required:** No

### Path Params

| Param | Type | Description |
|---|---|---|
| `scan_id` | `UUID` | Scan ID |

### Returns

ScanResponse

### Response Codes

- `200` — Success
- `404` — Scan not found

### Example Request

```bash
curl http://<HOST>/aisec-digital-risk/api/v1/scans/e5f6a7b8-c9d0-1234-ef56-789012345678
```

### Example Response `200` — Completed Scan

```json
{
  "id": "e5f6a7b8-c9d0-1234-ef56-789012345678",
  "target_id": "c3d4e5f6-...",
  "scan_type": "one_time",
  "scan_depth": "standard",
  "timeframe": "24 hours",
  "schedule_interval": null,
  "is_schedule_active": false,
  "parent_scan_id": null,
  "next_run_at": null,
  "status": "completed",
  "started_at": "2024-06-15T11:30:05Z",
  "completed_at": "2024-06-15T11:32:45Z",
  "processing_time_sec": 160.3,
  "total_results": 12,
  "new_articles_found": 8,
  "positive_count": 5,
  "negative_count": 3,
  "neutral_count": 4,
  "positive_pct": 41.7,
  "negative_pct": 25.0,
  "neutral_pct": 33.3,
  "overall_sentiment": "positive",
  "risk_summary": ["reputation_risk", "competitive_threat"],
  "security_alerts": [],
  "platform_breakdown": {"web": 9, "twitter": 2, "reddit": 1},
  "input_tokens": 45000,
  "output_tokens": 12000,
  "cost_usd": 0.035,
  "error_message": null,
  "retry_count": 0,
  "created_at": "2024-06-15T11:30:00Z"
}
```

---

## DELETE `/api/v1/scans/{scan_id}/schedule`

Cancels a scheduled scan and stops future executions. Historical results are preserved.

**Auth Required:** No

### Path Params

| Param | Type | Description |
|---|---|---|
| `scan_id` | `UUID` | Scheduled scan ID |

### Returns

MessageResponse

### Response Codes

- `200` — Schedule cancelled
- `404` — Scan not found
- `422` — Scan is not a scheduled scan

### Example Request

```bash
curl -X DELETE http://<HOST>/aisec-digital-risk/api/v1/scans/e5f6a7b8-.../schedule
```

### Example Response `200`

```json
{
  "success": true,
  "message": "Scheduled scan e5f6a7b8-... has been cancelled. Historical results are preserved."
}
```

---

# 4. Results

Results endpoints provide access to scraped and analyzed articles stored in the database.  
Articles are deduplicated by `(target_id, normalized_url)` — the same URL for the same target is stored only once,
regardless of how many scans found it.

---

## GET `/api/v1/results/target/{target_id}`

Returns all articles for a target across all scans.

**Auth Required:** No

### Path Params

| Param | Type | Description |
|---|---|---|
| `target_id` | `UUID` | Target ID |

### Query Params

| Param | Type | Default | Description |
|---|---|---:|---|
| `from_date` | `datetime or null` | `null` | Start date filter, ISO format (e.g. `2024-01-01T00:00:00`) |
| `to_date` | `datetime or null` | `null` | End date filter, ISO format |
| `sentiment` | `str or null` | `null` | Filter by: `"positive"`, `"negative"`, `"neutral"` |
| `platform` | `str or null` | `null` | Filter by: `"web"`, `"twitter"`, `"reddit"`, `"youtube"`, etc. |
| `limit` | `int (1-500)` | `100` | Max articles to return |
| `offset` | `int (>=0)` | `0` | Number of articles to skip |

### Returns ScanResultsResponse

| Field | Type | Description |
|---|---|---|
| `success` | `bool` | `true` |
| `scan_id` | `UUID or null` | `null` for target-level queries |
| `target_id` | `UUID` | Target ID |
| `total_count` | `int` | Total matching articles |
| `new_articles_found` | `int` | Always `0` for target-level queries |
| `scan_execution_time` | `float or null` | Always `null` for target-level queries |
| `articles` | `ArticleResponse[]` | Array of article objects |
| `sentiment_summary` | `dict or null` | Counts and percentages for positive, negative, neutral |
| `risk_summary` | `list or null` | Always `null` for target-level queries |
| `security_alerts` | `list or null` | Always `null` for target-level queries |
| `platform_breakdown` | `dict or null` | Article count per platform |
| `limit` | `int` | Applied limit |
| `offset` | `int` | Applied offset |
| `has_more` | `bool` | `true` if more results exist beyond current page |

### ArticleResponse Fields

| Field | Type | Description |
|---|---|---|
| `id` | `UUID` | Article unique ID |
| `target_id` | `UUID` | Associated target |
| `url` | `str` | Article URL |
| `title` | `str or null` | Article title |
| `source_name` | `str or null` | Source website name |
| `source_type` | `str or null` | Type of source (e.g. `"news"`, `"social"`) |
| `platform` | `str or null` | Platform (default `"web"`) |
| `author` | `str or null` | Author name |
| `published_date` | `date or null` | Publication date (YYYY-MM-DD) |
| `scraped_at` | `datetime or null` | When the article was scraped |
| `summary` | `str or null` | LLM-generated summary |
| `what_others_say` | `str or null` | What third parties say about the target in this article |
| `target_perspective` | `str or null` | How the article portrays the target |
| `key_quotes` | `list or null` | Notable quotes from the article |
| `snippet_content` | `str or null` | Short content excerpt |
| `sentiment` | `str or null` | `"positive"`, `"negative"`, or `"neutral"` |
| `sentiment_reasoning` | `str or null` | LLM explanation of sentiment classification |
| `headline_vs_body` | `str or null` | Whether headline sentiment matches body (`"match"`, `"mismatch"`) |
| `risk_flags` | `list or null` | Identified risk categories (e.g. `["reputation_risk"]`) |
| `risk_details` | `str or null` | Detailed risk description |
| `security_severity` | `str or null` | `"critical"`, `"high"`, `"medium"`, `"low"`, or `"none"` |
| `security_details` | `str or null` | Security finding details |
| `security_keywords` | `list or null` | Security-related keywords found |
| `content_completeness` | `str or null` | Quality indicator for scraped content |

### Response Codes

- `200` — Results retrieved
- `404` — Target not found

### Example Request

```bash
curl "http://<HOST>/aisec-digital-risk/api/v1/results/target/c3d4e5f6-...?sentiment=negative&limit=20"
```

### Example Response `200`

```json
{
  "success": true,
  "scan_id": null,
  "target_id": "c3d4e5f6-a7b8-9012-cdef-234567890abc",
  "total_count": 45,
  "new_articles_found": 0,
  "scan_execution_time": null,
  "articles": [
    {
      "id": "f6a7b8c9-d0e1-2345-f678-901234567890",
      "target_id": "c3d4e5f6-...",
      "url": "https://techcrunch.com/2024/06/15/apple-faces-eu-fine",
      "title": "Apple Faces Record EU Fine Over App Store Practices",
      "source_name": "TechCrunch",
      "source_type": "news",
      "platform": "web",
      "author": "Sarah Perez",
      "published_date": "2024-06-15",
      "scraped_at": "2024-06-15T11:31:20Z",
      "summary": "The European Commission has imposed a 1.8 billion euro fine on Apple...",
      "what_others_say": "Industry analysts have largely welcomed the EU decision...",
      "target_perspective": "Apple strongly disagrees with the ruling and plans to appeal...",
      "key_quotes": [
        "This is a landmark decision for digital market competition",
        "Apple believes the ruling ignores the benefits of its ecosystem"
      ],
      "snippet_content": null,
      "sentiment": "negative",
      "sentiment_reasoning": "The article describes a significant regulatory penalty against Apple.",
      "headline_vs_body": "match",
      "risk_flags": ["regulatory_risk", "financial_impact"],
      "risk_details": "Major regulatory fine with potential for additional enforcement actions.",
      "security_severity": "none",
      "security_details": null,
      "security_keywords": [],
      "content_completeness": "full"
    }
  ],
  "sentiment_summary": {
    "positive": 5,
    "negative": 20,
    "neutral": 10,
    "positive_pct": 14.3,
    "negative_pct": 57.1,
    "neutral_pct": 28.6
  },
  "risk_summary": null,
  "security_alerts": null,
  "platform_breakdown": {
    "web": 18,
    "twitter": 2
  },
  "limit": 20,
  "offset": 0,
  "has_more": true
}
```

---

## GET `/api/v1/results/scan/{scan_id}`

Returns articles discovered by a specific scan execution. Includes scan-level metadata such as
risk summary, security alerts, and execution time.

**Auth Required:** No

### Path Params

| Param | Type | Description |
|---|---|---|
| `scan_id` | `UUID` | Scan ID |

### Query Params

| Param | Type | Default | Description |
|---|---|---:|---|
| `limit` | `int (1-500)` | `100` | Max articles to return |
| `offset` | `int (>=0)` | `0` | Number of articles to skip |

### Returns

ScanResultsResponse — same structure as target results, but with these fields populated from the scan record:

- `scan_id` — the scan UUID
- `new_articles_found` — articles first discovered by this scan
- `scan_execution_time` — processing time in seconds
- `risk_summary` — aggregated risk flags from the scan
- `security_alerts` — security findings from the scan

### Response Codes

- `200` — Results retrieved
- `404` — Scan not found

### Example Request

```bash
curl "http://<HOST>/aisec-digital-risk/api/v1/results/scan/e5f6a7b8-...?limit=50"
```

---

# Complete Workflow Example

```
Step 1: Create a target
  POST /api/v1/targets/
       returns target_id

Step 2: Create a one-time scan
  POST /api/v1/scans/
       returns scan_id, status=pending

Step 3: Poll scan status (every 10-15 seconds)
  GET  /api/v1/scans/{scan_id}
       wait until status=completed

Step 4: Retrieve results
  GET /api/v1/results/scan/{scan_id}
       or
  GET /api/v1/results/target/{target_id}
```

## JavaScript Polling Example

```javascript
const BASE = "http://<HOST>/aisec-digital-risk";

async function pollScanStatus(scanId) {
  while (true) {
    const res = await fetch(`${BASE}/api/v1/scans/${scanId}`);
    const scan = await res.json();

    if (scan.status === "completed") {
      console.log(`Scan complete! Found ${scan.total_results} articles.`);
      return scan;
    }

    if (scan.status === "failed") {
      throw new Error(`Scan failed: ${scan.error_message}`);
    }

    // Still running — wait 15 seconds and retry
    await new Promise(r => setTimeout(r, 15000));
  }
}
```

---

# Error Response Format

All error responses follow this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

For validation errors (422):

```json
{
  "detail": [
    {
      "loc": ["body", "field_name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

# Common HTTP Status Codes

| Code | Meaning |
|---:|---|
| `200` | Success |
| `201` | Created |
| `404` | Not found |
| `409` | Conflict (duplicate normalized name) |
| `422` | Validation error |
| `500` | Internal server error |
| `503` | Service unavailable (database down) |

---

# Notes

- **No authentication required.** All endpoints are open.
- **Scan execution is asynchronous.** `POST /scans/` returns immediately. Poll `GET /scans/{scan_id}` until `status = "completed"`.
- **Search uses Whoogle.** A self-hosted Google proxy runs inside the same Docker network. Queries are rate-limited with a delay between executions to avoid Google blocks.
- **Scraping uses Crawl4AI.** Full article content is extracted using a headless browser with a plain-requests fallback for simple pages.
- **Three-layer deduplication.** Within each query (by page), across all queries (global URL set), and at the database level (normalized URL per target). The same article is never stored or analyzed twice.
- **Smart caching.** URLs already analyzed for a target in a previous scan are pulled from the database and linked to the new scan without re-scraping or re-analyzing.
- **Scheduled scans auto-repeat.** Once created, they run at the specified interval until cancelled via `DELETE /scans/{scan_id}/schedule`.
- **Soft deletes only.** Targets are deactivated, not permanently deleted. Historical data is always preserved.
- **Article `url` field** contains the original discovered URL. No normalized URL is exposed in responses.
