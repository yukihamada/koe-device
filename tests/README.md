# Koe Seed — Test Suite

## Quick Start

```bash
# Run against production (koe.live)
bash tests/test_api.sh

# Run against local dev server
bash tests/test_api.sh --local

# Skip admin-auth tests (no Fly.io access)
bash tests/test_api.sh --no-auth
```

## Requirements

- `curl` (comes with macOS/Linux)
- `python3` (for JSON parsing)
- `fly` CLI (only needed for authenticated admin tests — fetches `AUTH_TOKEN` from Fly.io)

## What Each Section Tests

| # | Section | Tests | What It Validates |
|---|---------|-------|-------------------|
| 1 | HTML Pages | 19 | All routed pages return HTTP 200 (`/`, `/order`, `/gallery`, `/pro`, `/busker`, etc.) |
| 2 | Page Content | 5 | Pages contain expected keywords (HTML tags, product names, pricing) |
| 3 | Health & JSON APIs | 7 | `/health` returns `{"status":"ok"}`, `/api/devices` returns array, `/api/stats`, `/api/features`, `/api/wt-hash`, `/api/rooms` |
| 4 | Stripe Checkout | 5 | Valid products (`deposit`, `dk_edition`, `seed`) create Stripe sessions; invalid product returns error; empty body returns 400 |
| 5 | Stripe Webhook | 2 | Webhook endpoint exists and rejects unsigned/invalid payloads |
| 6 | Admin Auth (No Token) | 3 | `/admin/orders`, `/admin/orders/export`, `PUT /admin/orders/:id` all return 401 without auth |
| 7 | Admin Operations | 6 | With auth: list orders, verify `.total` field, update notes, reject invalid status, CSV export with header row |
| 8 | Firmware / OTA | 2 | `/api/v1/device/firmware` responds (200/204/404); upload without token returns 401 |
| 9 | Static Assets | 2 | `favicon.svg` and static HTML files served correctly |
| 10 | Error Handling | 2 | Nonexistent path returns 404; wrong HTTP method returns 405 |

**Total: 53 tests**

## Adding New Tests

Use the helper functions defined at the top of `test_api.sh`:

```bash
# Check HTTP status code
assert_status "Test name" "$BASE/your/endpoint" "200"
assert_status "POST test" "$BASE/api/endpoint" "201" "POST" '{"key":"value"}'

# Check response body contains a string
assert_contains "Test name" "$BASE/page" "expected text"

# Check JSON field value
assert_json_field "Test name" "$BASE/api/endpoint" "field_name" "expected_value"

# Check JSON field exists
assert_json_exists "Test name" "$BASE/api/endpoint" "field_name"

# Authenticated request (uses $AUTH token)
assert_status_auth "Test name" "$BASE/admin/endpoint" "200"

# Skip a test with reason
skip_test "Test name" "reason"
```

## CI Integration

The script exits with the number of failures as the exit code:
- Exit 0 = all tests passed
- Exit N = N tests failed

```yaml
# GitHub Actions example
- name: E2E Tests
  run: bash tests/test_api.sh --no-auth
```

Note: `--no-auth` skips tests requiring `fly ssh` access. For full coverage, set up Fly.io CLI auth in CI or pass the token via environment variable.

## Endpoints Covered

### Pages (GET, expect 200)
`/`, `/order`, `/gallery`, `/business`, `/orchestra`, `/order/success`, `/admin`, `/pro`, `/busker`, `/classroom`, `/moji`, `/soluna-os`, `/stadium`, `/design`, `/compare`, `/crowd`, `/story`, `/app`, `/quickstart.html`

### JSON APIs
- `GET /health` — health check
- `GET /api/devices` — Soluna device list
- `GET /api/stats` — connection stats
- `GET /api/features` — feature flags
- `GET /api/wt-hash` — WebTransport cert hash
- `GET /api/rooms` — room list

### Stripe
- `POST /api/v1/checkout` — create checkout session
- `POST /api/v1/stripe/webhook` — webhook receiver

### Admin (requires `AUTH_TOKEN`)
- `GET /admin/orders` — order list (JSON)
- `PUT /admin/orders/:id` — update order
- `GET /admin/orders/export` — CSV export

### Firmware OTA
- `GET /api/v1/device/firmware?version=&device_id=` — check for updates
- `POST /api/v1/device/firmware/upload?version=&token=` — upload firmware
