# PON Integration Plan — Koe Sessions Digital Consent

**PON** is Enabler Inc.'s electronic contract and signature app.
This document covers the deeper integration once the PON app API becomes available.

---

## Current state (shipped)

The self-contained consent flow is live at `koe.live/consent/:token`:

| Route | Description |
|---|---|
| `GET /consent/:token` | Guest-facing consent page (`docs/consent.html`) |
| `GET /api/v1/consent/:token` | Check token status (pending / consented / revoked / invalid) |
| `POST /api/v1/consent/:token` | Guest signs (body: `{name, email?}`) |
| `POST /api/v1/consent/:token/revoke` | Revoke consent |
| `POST /api/v1/consent/generate` | Generate new token (admin Bearer auth) |
| `POST /api/v1/consent/pon-webhook` | PON webhook receiver (Bearer auth) |
| `GET /admin/consents` | List all consents (admin Bearer auth) |

DB table: `session_consents` (id, token, guest_name, guest_email, ip_addr, consented_at, revoked_at, created_at)

---

## Phase 1 — PON API webhook (when PON is ready)

### Trigger
When a guest signs the "Koe Sessions Recording Consent" contract inside the PON app,
PON POSTs to:

```
POST https://koe.live/api/v1/consent/pon-webhook
Authorization: Bearer <KOE_ADMIN_TOKEN>
Content-Type: application/json

{
  "token":        "<koe_consent_token>",   // embed in PON contract template
  "signer_name":  "Alex Rivera",
  "signer_email": "alex@example.com",
  "signed_at":    1751234567,              // unix timestamp
  "contract_id":  "pon-abc123"            // PON's own contract ID
}
```

### PON contract template fields
- **Contract name**: "Koe Sessions Recording Consent"
- **Koe token field**: hidden field pre-filled from QR code URL param `?token=xxx`
- **Signer fields**: full name (required), email (required by PON)
- **Property address**: pre-filled by host when generating the link
- **Recording period**: start date, end date (default: current stay)
- **Artist name**: who owns the recordings (pre-filled by host)
- **Consent text**: mirror the text in `docs/consent.html` for legal consistency

### Implementation steps
1. Create a dedicated `PON_WEBHOOK_SECRET` env var (distinct from `KOE_ADMIN_TOKEN`)
2. Update `handle_consent_pon_webhook` to verify using `PON_WEBHOOK_SECRET`
3. Set up Fly secret: `fly secrets set PON_WEBHOOK_SECRET=<secret> -a koe-live`
4. Register the webhook URL in PON dashboard: `https://koe.live/api/v1/consent/pon-webhook`
5. Test with PON test-mode signature

---

## Phase 2 — QR code on Stone device

Each Stone device can display a QR code (or NFC tag) so arriving guests can immediately scan and consent.

### Flow
```
Guest arrives
  → scans QR on Stone (or NFC)
  → opens koe.live/consent/<token>
  → reads terms, enters name, taps "I Agree"
  → consent stored in DB
  → Stone LED flashes violet to acknowledge
```

### Implementation steps
1. `POST /api/v1/consent/generate` → returns `{token, url}`
2. Host generates token, encodes `url` as QR, attaches printed QR to Stone
3. Stone firmware: on `/api/v1/consent/<token>` becoming `status: consented`, flash LED once
4. Optional: Stone e-ink display shows QR (future hardware revision)

### QR generation (host tooling)
```bash
# Generate token
TOKEN=$(curl -s -X POST https://koe.live/api/v1/consent/generate \
  -H "Authorization: Bearer $KOE_ADMIN_TOKEN" | jq -r .token)

# Print QR to terminal (requires qrencode)
qrencode -t ANSIUTF8 "https://koe.live/consent/$TOKEN"

# Or generate PNG
qrencode -o consent-qr.png "https://koe.live/consent/$TOKEN"
```

---

## Phase 3 — Session-scoped consent

Link consent tokens to specific `koe_sessions` records so the admin view shows "who consented before which session".

### Schema addition
```sql
ALTER TABLE session_consents ADD COLUMN session_id TEXT REFERENCES koe_sessions(id);
```

### Token generation
`POST /api/v1/consent/generate` accepts optional `{session_id}` in the request body.
The token is then associated with the session in DB.

### Admin view
`GET /admin/consents?session_id=xxx` returns consents scoped to a session.

---

## Phase 4 — Automated revoke on Stone tap

When any Stone tap is detected (`POST /api/v1/stone/:id/tap`), check if there is an active
session with a live consent, and if the tapping guest matches, auto-revoke.

This fulfils the promise: "touch any Stone to disable recording."

Current shortcut: any tap ends recording globally (via `koe_sessions.is_active`).
Consent revocation can mirror the same logic.

---

## Auth notes

- **Current**: all admin routes use `AUTH_TOKEN` env var via `verify_admin_auth()`
- **PON webhook**: currently also uses `KOE_ADMIN_TOKEN`; upgrade to `PON_WEBHOOK_SECRET` in Phase 1
- **Guest routes** (`/consent/:token`, `POST /api/v1/consent/:token`): no auth, token is the secret

---

## Env vars to add

| Var | Purpose | When |
|---|---|---|
| `PON_WEBHOOK_SECRET` | Dedicated HMAC secret for PON webhook | Phase 1 |
| `PON_API_KEY` | Koe → PON: create contracts via API | Phase 1 |
| `PON_TEMPLATE_ID` | ID of the "Koe Sessions" contract template in PON | Phase 1 |
