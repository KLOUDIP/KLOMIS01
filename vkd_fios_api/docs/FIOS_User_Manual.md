# FIOS Integration — User Manual & Test Guide

Odoo 19 · Modules: `vkd_fios_api`, `vkd_fios_signup`, `vkd_subscription_handling`

---

## 1. Concepts (read first)

| Concept | Meaning |
|---------|---------|
| **Service Tier** | FIOS / FIOS Lite / FIOS Premium. **Each tier is a separate FIOS account with its own API token and creator id.** A customer belongs to exactly **one** tier. |
| **FIOS Service** | The billable thing a product provisions on FIOS: **Units** (`avl_unit`), **Users** (`storage_user`), **Geofences** (`zones_library`), **Google Maps** (`own_google_service`), **Ecodriving** (`ecodriving`), **Data Streaming** (`avl_retranslator`). |
| **Quantity vs Feature service** | *Quantity* (Units/Users/Geofences): the subscribed quantity becomes the limit. *Feature* (Maps/Ecodriving/Streaming): enabled when purchased, disabled when removed. |
| **Provision-at-purchase** | Registration only creates the Odoo user. The **FIOS account is created after the first purchase**, under the purchased product's tier, **in the background**. |
| **Days** | The FIOS block-by-days counter is set from the subscription's **next invoice date** (no fixed trial days). |

**End-to-end flow:**
```
Register (Odoo user only, "registered")
   → Buy a tier product (checkout returns instantly)
   → Background cron provisions the FIOS account under that tier
        create_user → user_flags(4) → create_resource → create_account(plan)
        → batch(default services + block-by-days) → set limits from products
        → set days from next_invoice_date  → state "active"
   → Add / reduce services  → limits re-synced to FIOS
   → Non-payment / close     → account disabled when no active subscription remains
```

---

## 2. Configuration (do this first)

### 2.1 Service Tiers — **FIOS → Service Tiers**
Create one record per tier. A default **FIOS** tier is seeded from placeholder test values — **replace the token/creator id with real ones**.

| Field | Example | Notes |
|-------|---------|-------|
| Name | `FIOS Lite` | Display name |
| Code | `lite` | Unique |
| Base URL | `https://fios-api.kloudip.com` | |
| API Token | *(from FIOS)* | The tier's login token (masked field) |
| Creator ID | *(from FIOS)* | The tier's top-level creator user id |
| Billing Plan Code | `kloudip3` | Passed to `account/create_account` |

Add **FIOS**, **FIOS Lite**, **FIOS Premium** tiers, each with its own token / creator id / plan code.

### 2.2 Products & FIOS mapping — **Sales → Products**
On each product's form (General Information), set:
- **FIOS Service Tier** → which tier this product belongs to (FIOS / Lite / Premium).
- **FIOS Service** → which service it provisions (Units / Users / Geofences / Google Maps / Ecodriving / Data Streaming).
- Make it a **recurring/subscription** product (has a recurring price / subscription plan).

> A product is treated as a "FIOS product" (and gated) when its **FIOS Service Tier** is set. The **tier** identifies/gates the product and decides the token; the **service** decides which limit it feeds. A **combo needs only the tier** (no service); the combo's item products carry the services.

### 2.3 System Parameters — **Settings → Technical → System Parameters**

| Key | Default | Purpose |
|-----|---------|---------|
| `vkd_fios_api.keepalive_active` | `1` | Enable the session keep-alive cron |
| `vkd_fios_api.account_flags` | `32` | Account block-by-days flag |
| `vkd_fios_api.signup_otp_enabled` | `1` | Require email OTP on public signup |
| `vkd_fios_api.signup_otp_debug` | `0` | **TEST ONLY** — show the OTP on screen (staging without mail). Keep `0` in production |
| `vkd_fios_api.pwd_secret` | *(auto)* | Encryption key for the pending signup password (auto-generated) |

For OTP email to send, configure an **Outgoing Mail Server** (Settings → Technical). On staging without mail, set `signup_otp_debug = 1`.

### 2.4 Scheduled Actions (auto-created) — **Settings → Technical → Scheduled Actions**
- **FIOS: Session Keep-Alive** — every 4 min (keeps each tier's session alive).
- **FIOS: Retry Failed API Calls** — every 15 min.
- **FIOS: Process Pending Provisioning** — every 2 min (background account creation after purchase).

---

## 3. Recommended test setup (with a combo)

Create **service products** (one per service), all: recurring, **FIOS Service Tier = FIOS Lite**, price as you like:

| Product | FIOS Service |
|---------|--------------|
| Lite Units | Units / Devices (`avl_unit`) |
| Lite Users | Users (`storage_user`) |
| Lite Geofences | Geofences (`zones_library`) |
| Lite Google Maps | Google Maps (`own_google_service`) |

Then create a **Combo** to sell them as one bundle:
1. **Sales → Products → Combo Choices** — create a combo "Lite Bundle Items" and add the service products as combo items (set quantity per item if needed).
2. Create a **combo product** "FIOS Lite Bundle" (Product Type = *Combo*), attach the combo choice, make it recurring, set **FIOS Service Tier = FIOS Lite**.
3. Publish the products on the website (Website → eCommerce).

> **Combos:** set **only the FIOS Service Tier** on the **combo product** (no FIOS Service). The tier is enough to identify/gate the combo and pick the token — same idea as Trazet keying the combo. The combo's **item products** carry the **FIOS Service** (recurring) so each item feeds its own service limit. So: **combo → tier only; combo items → service (+ tier)**.

Repeat with a **Premium** set to test tier mutual-exclusion.

---

## 4. Views reference

### Backend — **FIOS** menu (System users)
| View | Where | Purpose |
|------|-------|---------|
| **Service Tiers** | FIOS → Service Tiers | Manage tier tokens/creator/plan |
| **Import Accounts** | FIOS → Import Accounts | Wizard to link existing FIOS accounts |
| **API Log** | FIOS → API Log | Every FIOS call (success/failed/pending) with params/response, **Retry Now** |
| **Sessions** | FIOS → Sessions | Live SIDs per tier |

### Backend — Contact form **FIOS tab** (a contact that is a FIOS customer)
- **Header buttons:** **Provision / Resume** (create/repair + re-sync), **Refresh FIOS Status** (read live status + usage), **Refresh Devices** (list units).
- **Status:** Is FIOS User, Service Tier, Provisioning state, Provisioning Pending, Last Sync.
- **FIOS Identifiers:** User ID, Resource ID, Account Item ID.
- **Last Error** (only if any).
- **Live Account Status:** Enabled, Plan, Days Left, Balance, **Service Usage table** (Service / Used / Limit / Enabled), Status Read At.
- **FIOS Devices:** Device/Plate, IMEI, Phone, Activated.

### Product form
FIOS Service Tier, FIOS Service (General Information tab).

### Website / Portal
| View | URL | Purpose |
|------|-----|---------|
| **Sign-up** | `/fios-signup` | Register (name, company, email, phone, password) |
| **Verify email** | (after signup) | Enter OTP; **Resend code** |
| **My FIOS Services card** | `/my/home` | Card shown only to provisioned FIOS customers |
| **FIOS services + usage** | `/my/fios-services` | Plan, days, status, per-service Used/Limit table |

---

## 5. Workflow details

### 5.1 Registration
Public visitor adds a FIOS product → gate redirects to **/fios-signup** → fills the form → (if OTP on) receives a 6-digit code → verifies → Odoo user created (`is_fios_user`, state **registered**) → sent to log in → returns to cart. **No FIOS account yet.**

### 5.2 Purchase → provisioning (background)
On subscription confirmation, the partner is stamped with the product's **tier** and **Provisioning Pending = True**. Checkout returns immediately. Within ~2 min the cron provisions the FIOS account and pushes limits + days. State becomes **active**; the pending flag clears.

### 5.3 Add / reduce services
- **Add** (upsell): limit = **current qty + newly added qty**, pushed to FIOS.
- **Reduce** (portal): checked against live **usage** first (see 6.4).

### 5.4 Reduce with usage guard
- Limit 10, used 5, reduce to 6 → allowed → limit set to **6**.
- Limit 10, used 10, reduce → **blocked** with: *"Cannot reduce … you are currently using 10. Please log in to FIOS, delete the unwanted items … then come back and reduce."*

### 5.5 Tier mutual-exclusion
A customer on **Lite** cannot add a **Premium** product (blocked at add-to-cart / checkout with a tier warning). Tier changes are **manual** (move the account in FIOS, then change **Service Tier** on the contact).

### 5.6 Close / non-payment
Closing a subscription recomputes limits; if the customer has **no active subscription left**, the FIOS account is **disabled** (`enable_account: 0`). Buying again re-enables it.

### 5.7 Import existing FIOS customers — **FIOS → Import Accounts**
1. Select a **Service Tier** → **Fetch Accounts** (lists that tier's accounts via its token).
2. For each row set the **Odoo Customer** (manual match by account name; already-linked rows are read-only).
3. **Import Selected** → links partner + FIOS ids + tier, marks **active**. No FIOS calls.

---

## 6. Test cases

> Prereq: tiers configured with **working** tokens; Lite & Premium service products + combos published; an outgoing mail server (or `signup_otp_debug=1`).

| # | Scenario | Steps | Expected result |
|---|----------|-------|-----------------|
| **T1** | Public gate → signup | Log out. Add a Lite product to cart | Redirected to `/fios-signup` |
| **T2** | OTP verify | Submit signup form | OTP page; correct code → user created (`registered`); redirected to login → cart. **No API log yet** |
| **T3** | OTP wrong/resend | Enter wrong code ×; Resend | "Incorrect code" (5 tries), 60s resend cooldown |
| **T4** | Purchase provisions | Log in, buy the Lite combo, pay | Checkout returns fast. Within ~2 min: partner state **active**; **API Log** shows create_user → update_user_flags → create_resource → create_account → core/batch |
| **T5** | Days from invoice | After T4, open contact → Refresh FIOS Status | Days Left ≈ (next invoice − today); `do_payment` in API Log with that delta |
| **T6** | Limits from products | After T4 | `avl_unit`/`storage_user`/`zones_library` limits = purchased quantities (usage table) |
| **T7** | Add service | Upsell: add more Units | Limit rises to current + added; core/batch update in API Log |
| **T8** | Reduce (allowed) | Units limit 10, usage 5 (create 5 units in FIOS), reduce to 6 | Allowed; limit set to 6 |
| **T9** | Reduce (blocked) | Units limit 10, usage 10, reduce | Warning banner: go to FIOS, delete devices, come back |
| **T10** | Feature service | Buy Google Maps product | `own_google_service` enabled; remove → disabled |
| **T11** | Tier exclusion | As a Lite customer, add a Premium product | Blocked at cart/checkout with tier warning |
| **T12** | Close → disable | Close the only subscription | Account **disabled** on FIOS (Refresh Status → Enabled = false) |
| **T13** | Devices list | Contact → Refresh Devices | Lists units (Name/IMEI/Phone/Activated) |
| **T14** | Portal usage | Customer portal → My FIOS Services | Card on `/my/home`; usage table on `/my/fios-services` |
| **T15** | Import | FIOS → Import Accounts → pick tier → Fetch → match → Import | Partner linked, state active, tier set |
| **T16** | Resume after failure | If a purchase provision failed, click **Provision / Resume** | Resumes (create_account handles "already exists"), completes to active |
| **T17** | Keep-alive | Wait > 5 min idle, then any FIOS action | Session auto re-logs in (see Sessions / API Log) |