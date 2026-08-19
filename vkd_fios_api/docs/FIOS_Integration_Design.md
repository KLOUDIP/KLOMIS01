# FIOS API Integration — Design Document

**Module:** `vkd_fios_api` (Odoo 19) — standalone module
**Author:** VK DATA ApS
**Status:** Draft
**Date:** 2026-07-28

---

## 1. Purpose & Scope

Provision and manage customer accounts on the **FIOS** platform (a Wialon-based GPS/fleet
telematics system) directly from Odoo. When a customer/subscription is created or changed in
Odoo, the corresponding **User → Resource → Account** must be created on FIOS, and its billing
services, limits, payments and enable/disable state kept in sync.

This is a **new, self-contained integration** distinct from the existing Trazet platform
integration (`vkd_trazet_api`, `euapi.trazet.com`). FIOS lives at
`https://fios-api.kloudip.com` and speaks the classic Wialon `ajax.html` protocol. It is
delivered as its own module, `vkd_fios_api`, with **no dependency** on `vkd_trazet_api`.

### In scope
- FIOS session lifecycle (token → SID, keep-alive, re-login).
- Customer account provisioning flow (create user, resource, account).
- Post-provisioning operations: billing services / limits, payments, enable-disable, account data.
- Persistence of FIOS identifiers on Odoo records; portal-user identification via `is_fios_user`.
- Error handling & retry via an own `fios.api.log` model (mirrors Trazet's `api.retry.log`).

### Out of scope (this iteration)
- Unit/device provisioning on FIOS.
- Real-time telematics event consumption (`avl_evts` is used **only** for keep-alive here).
- The Product → Billing Plan mapping values (must be agreed with FIOS — see §8).

---

## 2. FIOS API Primer

All calls follow:

```
GET/POST https://fios-api.kloudip.com/wialon/ajax.html?svc=<service>&params=<url-encoded-JSON>&sid=<SID>
```

`params` is a JSON object, URL-encoded. Responses are JSON. **Wialon returns HTTP 200 even on
logical errors** — failures are signalled by an `{"error": <code>}` body, so success cannot be
judged by status code alone (see §7).

### 2.1 Authentication — obtaining the SID

```
svc=token/login
params={"token":"<LONG_LIVED_TOKEN>","fl":1}
```

Response (relevant fields):

| Field       | Meaning                                             |
|-------------|-----------------------------------------------------|
| `eid`       | **Session ID (SID)** — pass as `sid=` on every call |
| `au`        | Authenticated user name (e.g. `mis_api_demo`)       |
| `base_url`  | Underlying Wialon host                              |
| `tm`        | Server timestamp                                    |

### 2.2 Session keep-alive

- The session is killed after **5 minutes** of inactivity.
- Keep alive with: `GET https://fios-api.kloudip.com/avl_evts?sid=<SID>`
- Constraint: **≤ 10 `avl_evts` requests per 10 seconds**.
- On expiry (error code 1 "Invalid session"), transparently re-login and retry once.

### 2.3 Provisioning services

| Step | `svc`                    | Key `params`                                                        | Save from response |
|------|--------------------------|--------------------------------------------------------------------|--------------------|
| 1    | `core/create_user`       | `creatorId`, `name`, `password`, `dataFlags:5`                     | `id` → **user_id** |
| 2    | `core/create_resource`   | `creatorId` (= user_id), `name`, `skipCreatorCheck:0`, `dataFlags:5` | `id` → **resource_id** |
| 3    | `account/create_account` | `itemId` (= resource_id), `plan`                                    | account is on the resource item |

**Password policy** (validate before calling `create_user`): ≥ 8 chars, ≥ 1 uppercase,
≥ 1 lowercase, ≥ 1 digit, ≥ 1 special char, and **not equal** to the username.

### 2.4 Post-provisioning services

| Operation            | `svc`                            | Notable params |
|----------------------|----------------------------------|----------------|
| Get account data     | `account/get_account_data`       | `itemId`, `type:2` |
| Set limits / block   | `core/batch` wrapping several `account/update_billing_service` + `account/update_flags` | `costTable`, `intervalType`, `flags` |
| Make payment         | `account/do_payment`             | `balanceUpdate`, `daysUpdate`, `description` |
| Enable / disable     | `account/enable_account`         | `enable` (0/1) |
| Single service limit | `account/update_billing_service` | `name` (e.g. `avl_unit`), `costTable` |

---

## 3. Module Layout (`vkd_fios_api`)

Standalone module, no dependency on `vkd_trazet_api`. Depends only on `base` (and `sale` /
`sale_subscription` if provisioning is triggered from subscriptions — see §12 Q1).

```
vkd_fios_api/
├── __manifest__.py            # depends: ['base', 'sale', 'sale_subscription']
├── __init__.py
├── data/
│   ├── ir_config_parameter.xml   # FIOS creds/urls (placeholders only)
│   └── ir_cron_data.xml          # keep-alive + retry crons
├── models/
│   ├── __init__.py
│   ├── fios_session.py           # SID cache
│   ├── fios_api_client.py        # transport + session mgmt
│   ├── fios_provisioning.py      # User→Resource→Account orchestration
│   ├── fios_api_log.py           # own retry/ops log
│   ├── res_partner.py            # is_fios_user + FIOS identifiers
│   ├── res_users.py              # is_fios_user (mirror of Trazet pattern)
│   └── product_template.py       # fios_plan_code
├── security/
│   └── ir.model.access.csv
└── views/
    ├── res_partner_views.xml
    ├── res_users_views.xml
    ├── fios_api_log_views.xml
    └── product_template_views.xml
```

---

## 4. High-Level Architecture

```
                         Odoo (vkd_fios_api)
   ┌───────────────────────────────────────────────────────────────┐
   │                                                                 │
   │  res.partner / sale.order  ──triggers──►  fios.provisioning     │
   │   (is_fios_user + FIOS ids)                (orchestration)      │
   │                                                │                │
   │                                                ▼                │
   │                                        fios.api.client          │
   │                                   (transport + SID mgmt)        │
   │                                                │                │
   │            ir.config_parameter ◄──creds──┐     │                │
   │            fios.session (SID cache) ◄─────┘     │                │
   │                                                │                │
   │  ir.cron: FIOS keep-alive (every 4 min)  ──────┤                │
   │  fios.api.log (own retry log) ◄──failures──────┘                │
   └────────────────────────────────────────────────┼───────────────┘
                                                     ▼
                                      https://fios-api.kloudip.com
```

Layering keeps concerns separate:
1. **Transport / session** (`fios.api.client`) — knows nothing about customers.
2. **Orchestration** (`fios.provisioning`) — the User→Resource→Account sequence and business rules.
3. **Odoo domain models** — flags + identifiers + triggers on `res.partner` / `res.users` / `sale.order`.

---

## 5. Configuration (`ir.config_parameter`)

Own `vkd_fios_api.*` key namespace. **Do not commit real production secrets** — ship
placeholders / dev values only.

| Key                             | Purpose                              | Example (dev)                        |
|---------------------------------|--------------------------------------|--------------------------------------|
| `vkd_fios_api.base_url`         | FIOS base URL                        | `https://fios-api.kloudip.com`       |
| `vkd_fios_api.token`            | Long-lived login token               | `9652a1976...` (test token)          |
| `vkd_fios_api.creator_id`       | Top-level creator user system ID     | `27557881`                           |
| `vkd_fios_api.keepalive_active` | Toggle keep-alive cron behaviour     | `1`                                  |

> The provisioning docs show a `creatorId` of `27557881` for the user step and `30416577`
> (the newly created user) for the resource step. Only the **top-level** creator id is a
> configuration value; the resource's creator id is the runtime user_id from Step 1.

---

## 6. Data Model

### 6.1 `fios.session` (SID cache)

Persists the active SID so it survives worker restarts and is shared across workers/crons.

| Field           | Type     | Notes                                    |
|-----------------|----------|------------------------------------------|
| `sid`           | Char     | Current session id (`eid`)               |
| `auth_user`     | Char     | `au` from login response                 |
| `login_time`    | Datetime | When the SID was obtained                |
| `last_activity` | Datetime | Updated on every successful call / ping  |
| `active`        | Boolean  | Whether this SID is believed valid       |

Only one active row is expected; the client reads the latest active row and invalidates it on
session-expiry errors.

### 6.2 `res.users` — `is_fios_user` (mirror of Trazet)

Mirroring `is_trazet_user`, add a boolean on the portal user for **identification / eligibility**.
This is what lets you filter "which portal users are FIOS-provisioned", drive views, and scope
security. It carries no FIOS system id itself — that lives on the partner (§6.3).

| Field          | Type    | Notes                                             |
|----------------|---------|---------------------------------------------------|
| `is_fios_user` | Boolean | Portal user is a FIOS customer (mirror of `is_trazet_user`) |

> **Rationale (per review):** keep the flag on **both** `res.users` and `res.partner`, exactly as
> Trazet does with `is_trazet_user`. The user flag identifies the portal login; the partner holds
> the commercial identifiers. Work resolves through `partner.user_ids[0]` when a user context is
> needed, consistent with the existing Trazet code.

### 6.3 `res.partner` — flag + FIOS identifiers

| Field                    | Type      | Notes                          |
|--------------------------|-----------|--------------------------------|
| `is_fios_user`           | Boolean   | Mirror of user flag (copy=False) |
| `fios_user_id`           | Char      | Step 1 result                  |
| `fios_resource_id`       | Char      | Step 2 result                  |
| `fios_account_item_id`   | Char      | = resource id (account lives on resource) |
| `fios_provision_state`   | Selection | `not_started/user_created/resource_created/account_created/failed` |
| `fios_last_sync`         | Datetime  | Last successful sync           |
| `fios_last_error`        | Text      | Last failure detail            |

A per-step state machine makes the flow **resumable**: if Step 3 fails, a re-run skips Steps 1–2.

### 6.4 `product.template` — `fios_plan_code`

`Char` field carrying the FIOS `plan` code per product (see §8).

### 6.5 `fios.api.log` (own retry / ops log)

Standalone equivalent of Trazet's `api.retry.log`, kept **inside this module** so `vkd_fios_api`
has no cross-module dependency. Same shape and exponential-backoff retry cron, FIOS-specific
`svc` field instead of Trazet's PATCH URL.

| Field              | Type      | Notes                                        |
|--------------------|-----------|----------------------------------------------|
| `svc`              | Char      | FIOS service, e.g. `core/create_user`        |
| `params`           | Text      | JSON params (scrubbed of secrets)            |
| `partner_id`       | Many2one  | `res.partner`                                |
| `state`            | Selection | `pending/success/failed`                     |
| `retry_count`      | Integer   | Backoff counter                              |
| `next_retry_time`  | Datetime  | Backoff schedule                             |
| `response_data`    | Text      | Parsed FIOS response                         |
| `last_error`       | Text      | Error code/message                           |

> **Decision:** own `fios.api.log` (Option A). Rejected Option B (depend on `vkd_trazet_api` and
> extend `api.retry.log`) because it would couple FIOS to the Trazet module and its token config.
> If a single unified "all outbound API calls" ops screen is later required, revisit.

---

## 7. `fios.api.client` — Transport & Session Layer

An `AbstractModel`/`TransientModel` helper exposing a single `call()` entry point.

```python
def call(self, svc, params, retry_on_expiry=True):
    """Execute a FIOS svc. Returns parsed dict.
    Raises FiosApiError on {"error": ...} responses."""
    sid = self._get_sid()                      # cached or fresh login
    url = f"{base}/wialon/ajax.html"
    resp = requests.post(url, data={
        "svc": svc,
        "params": json.dumps(params),
        "sid": sid,
    }, timeout=30)
    data = resp.json()
    if isinstance(data, dict) and "error" in data and data["error"] != 0:
        if data["error"] == 1 and retry_on_expiry:   # invalid/expired session
            self._invalidate_sid()
            return self.call(svc, params, retry_on_expiry=False)  # one retry
        raise FiosApiError(data["error"], svc, params)
    self._touch_session()
    return data
```

Design notes:
- **Prefer POST** over GET so the token/params are not logged in URLs/proxies.
- **Single re-login retry** on session-expiry only (avoid infinite loops).
- `_get_sid()` reads `fios.session`; if missing/expired, performs `token/login`, stores the SID.
- All params JSON-encoded exactly once; ints stay ints (Wialon is type-sensitive).

### 7.1 Keep-alive cron

`ir.cron` "FIOS Session Keep-Alive", every **4 minutes** (safely under the 5-min timeout):

```python
@api.model
def cron_fios_keepalive(self):
    session = self._get_active_session()
    if not session:
        return  # nothing to keep alive; next real call will login
    try:
        requests.get(f"{base}/avl_evts", params={"sid": session.sid}, timeout=15)
        session.last_activity = fields.Datetime.now()
    except Exception:
        session.active = False  # force re-login on next use
```

Respect the ≤10-per-10s ceiling — a single 4-minute cron is far within limits.

---

## 8. Error Handling

Wialon error codes (subset relevant here):

| Code | Meaning                        | Handling                                        |
|------|--------------------------------|-------------------------------------------------|
| 0    | OK                             | success                                         |
| 1    | Invalid session                | invalidate SID, re-login, retry once            |
| 4    | Invalid input / wrong params   | do **not** retry; log, mark provisioning failed |
| 5    | Error performing request       | retryable via `fios.api.log`                    |
| 7    | Access denied                  | config/permissions issue; alert, no auto-retry  |
| 8    | Invalid user name/password     | validation problem; surface to user             |
| 14   | Billing/limit related          | surface with account context                    |

Rules:
- **Never infer success from HTTP 200** — always parse the body.
- **Transient** errors (network, code 5) → create `fios.api.log` (pending) for backoff retry.
- **Permanent** errors (code 4/7/8) → mark `fios_provision_state = failed`, store `fios_last_error`, stop.
- Provisioning is **sequential; stop on first failure** (per FIOS docs).

---

## 9. Product → Billing Plan Mapping (OPEN)

FIOS docs define only `Testing → kloudip3`. FIOS Lite / Premium / Enterprise are **"To be mapped"**.

Approach: `product.template.fios_plan_code` holds each product's FIOS plan; `fios.provisioning`
reads it from the subscription's plan product.

**Action required from FIOS/business:** confirm the real plan codes before go-live.

| Odoo Product        | FIOS `plan` code |
|---------------------|------------------|
| Testing             | `kloudip3`       |
| FIOS Lite           | *TBD*            |
| FIOS Premium        | *TBD*            |
| FIOS Enterprise     | *TBD*            |

---

## 10. Provisioning Orchestration (`fios.provisioning`)

Triggered when a partner/subscription needs a FIOS account (exact trigger TBD — likely on sale
order confirmation, mirroring existing Trazet `action_confirm` hooks). Eligible partners are those
whose linked user has `is_fios_user = True`.

```
def provision_account(partner):
    if partner.fios_provision_state == 'account_created':
        return  # idempotent
    # Step 1
    if not partner.fios_user_id:
        pwd = generate_valid_password(partner)        # meets §2.3 policy
        r = client.call('core/create_user', {
            'creatorId': int(config.creator_id),
            'name': fios_username(partner),
            'password': pwd, 'dataFlags': 5})
        partner.fios_user_id = r['id']
        partner.fios_provision_state = 'user_created'
        store_credentials(partner, pwd)               # securely
    # Step 2
    if not partner.fios_resource_id:
        r = client.call('core/create_resource', {
            'creatorId': int(partner.fios_user_id),
            'name': partner.commercial_company_name or partner.name,
            'skipCreatorCheck': 0, 'dataFlags': 5})
        partner.fios_resource_id = r['id']
        partner.fios_account_item_id = r['id']
        partner.fios_provision_state = 'resource_created'
    # Step 3
    client.call('account/create_account', {
        'itemId': int(partner.fios_account_item_id),
        'plan': resolve_plan_code(partner)})
    partner.fios_provision_state = 'account_created'
    partner.fios_last_sync = now()
```

Each `client.call` wrapped so a failure records `fios.api.log` + sets state, then aborts.

Post-provisioning helpers (`set_billing_services`, `make_payment`, `enable_account`,
`get_account_data`) map 1:1 to §2.4 and reuse `client.call` / `core/batch`.

---

## 11. Security & Secrets

- FIOS token and creator id in `ir.config_parameter` (System-only read), **not** in source.
- Generated FIOS user passwords: store encrypted / in a restricted field, or don't persist at all
  if not needed after creation. Decide with security review.
- Never log the token or full `params` containing credentials at INFO level.
- Prefer POST to avoid secrets in access logs.
- `is_fios_user` / FIOS fields on `res.partner` & `res.users`: readable by internal users; FIOS
  identifiers not exposed to the portal.

---

## 12. Delivery Plan

| Phase | Deliverable                                                            |
|-------|-----------------------------------------------------------------------|
| 0     | Module skeleton `vkd_fios_api` (manifest, dirs, security)             |
| 1     | Config params + `fios.session` + `fios.api.client` (login, call, keep-alive cron) |
| 2     | `is_fios_user` on `res.users` + `res.partner` FIOS fields + `fios.provisioning` (Steps 1–3) |
| 3     | Post-provisioning ops (batch limits, payment, enable/disable, account data) |
| 4     | `fios.api.log` + backoff cron + views (FIOS state/errors on partner & user forms) |
| 5     | Billing-plan mapping via `product.template.fios_plan_code` (pending FIOS codes) |

Each phase independently testable against the FIOS test token.

---

## 13. Open Questions

1. **Trigger point** — provision on SO confirmation, on the `is_fios_user` flag, or an explicit button?
2. **Billing plan codes** for Lite / Premium / Enterprise (blocks Step 3 for real products).
3. **Username scheme** for FIOS users (email? partner ref? uniqueness/collision handling).
4. **Password persistence** — does FIOS/customer need it after creation, or is it write-only?
5. **Production credentials** — real token + creator id (docs use `mis_api_demo` test values).
6. **GET vs POST** — confirm FIOS proxy accepts POST form-encoded `svc/params/sid`.
7. **Default billing services & values** — the batch example uses specific `costTable` strings
   (`zones_library 5:0;-1`, `avl_unit 5:0;-1`, `storage_user 2:0;-1`, flags 32). Standard defaults
   for every new account, or plan-dependent?
8. **Unified ops log?** — keep `fios.api.log` standalone (current decision) or later merge with
   Trazet's `api.retry.log` for one screen?
```