# vkd_lk_account_tax_report — v17 → v19

The module was still shipping as `17.0.1.2.9` and had never been adapted to
Odoo 19's report layout. Now `19.0.1.0.0`.

Comparing your two pairs of PDFs:

| | v17 (`…KLRV_00368`, `…KLRV_00370`) | v19 (`…KLRV_00379`, `…KLRV_00397`) |
|---|---|---|
| Boxed **Tax Invoice** / **Tax Credit Note** title | present | **missing** |
| Company name in header | `KLOUDIP (PVT) LTD` | **missing** |
| `Tax ID: 174708878` in header | absent | present |
| Document number | `26AUG_KLRV_00368` | `26/08_KLRV_00379` (raw sequence) |
| Tax figures | SSCL 2.5% / VAT 18% | identical ratios — unaffected |

Three separate causes.

---

## 1. The missing title — the `-70px` offset

`report_styles.css` had:

```css
.lk-invoice { margin-top: -70px !important; padding-top: -70px !important; }
```

That offset existed to claw back the vertical space left by the standard
address block, which the template tried to hide with:

```css
div[name="address"]           { display: none !important; }
div[name="information_block"] { display: none !important; }
```

In Odoo 19 those selectors match nothing. `address` and `information_block`
stopped being divs with those names and became **QWeb variables**, set with
`<t t-set="address">` inside `account.report_invoice_document` and rendered by
`web.external_layout` through `web.address_layout` — above the report body,
alongside a new `<h2 t-out="layout_document_title"/>`.

So in v19 the address block renders at full height *and* the page is still
pulled up 70px. The title box ends up above the printable area and wkhtmltopdf
drops it.

**Fix.** Stop hiding markup and blank the variables instead, in the inheriting
template:

```xml
<t t-set="address" t-value="''"/>
<t t-set="information_block" t-value="''"/>
<t t-set="layout_document_title" t-value="''"/>
<t t-call="vkd_lk_account_tax_report.report_invoice_document_lk"/>
```

This runs while the `t-call` body is being rendered — QWeb renders the body into
`0` before invoking the called template — so `external_layout` sees the blanked
values. No gap is left, so `.lk-invoice` goes to `margin-top: 0` and the title
box comes back.

(`padding-top: -70px` was never valid CSS: negative padding is ignored by every
renderer. It was doing nothing even in v17.)

---

## 2. The missing company name — configuration, not code

`web.external_layout_standard` in Odoo 19:

```xml
<li t-if="company.is_company_details_empty">
    <span t-field="company.partner_id"
          t-options='{"widget": "contact", "fields": ["address", "name"], ...}'/>
</li>
<li t-else="">
    <span t-field="company.company_details"/>
</li>
<li t-if="not forced_vat">
    <t t-if="company.vat"><t t-esc="…or 'Tax ID'"/>: <span t-esc="company.vat"/></t>
</li>
```

When **Company Details** is filled in, v19 prints that free text *instead of* the
partner contact block — and the contact block is what used to supply the company
name. Your Company Details evidently holds the address lines only, which is
exactly what the new PDFs show. The `Tax ID:` line is new in v19 and always
printed when the company has a VAT number.

**Fix:** Settings → Users & Companies → Companies → KLOUDIP (Pvt) Ltd →
**Company Details**, and put `KLOUDIP (PVT) LTD` on the first line above the
address. No code change; nothing in the module can override this cleanly.

If you would rather not have the `Tax ID:` line, it is suppressed by setting a
`forced_vat`, but the honest option is to leave it — it is a legitimate part of
the v19 standard header.

---

## 3. The document number falling back to the raw sequence

The template built the number as `yy + MMM + '_' + journal code + '_' + digits`,
but only inside:

```xml
<t t-if="o.state == 'posted' and o.invoice_date and o.name and o.name != '/'">
```

Every render where `state != 'posted'` — a preview, a proforma, anything printed
before posting — silently fell to the `t-else` and printed `o.name` raw. That is
`26/08_KLRV_00379` instead of `26AUG_KLRV_00379`.

Note your v17 credit note `26/07_KLRV_00370` shows the same raw form, so this is
not purely a v19 regression — it is a long-standing condition that is simply
being hit more often now.

**Fix.** `o.state == 'posted'` is dropped. It added nothing: an unposted move has
no real name, which `o.name and o.name != '/'` already covers.

---

## What was deliberately left alone

`_compute_vat_18_amount` and `_compute_tax_breakdown` still use
`account.tax.compute_all()`. Odoo 18/19 introduced a new tax API
(`_prepare_base_line_for_taxes_computation` / `_add_tax_details_in_base_line`),
and `compute_all` is legacy — but your v17 and v19 PDFs print **identical tax
ratios** (SSCL 2.564% of net, VAT 18%), so it is still behaving correctly here.
Rewriting a tax computation blind, on invoices that are already correct, is not
a trade worth making. Worth scheduling as tech debt, not as part of this fix.

The `account.move` and `account.journal` view inherits were also left alone: the
module installs and the report renders, so those xpaths still resolve.

---

## Deploy and verify

```
-u vkd_lk_account_tax_report
```

Then, before trusting the PDF, look at the HTML — it renders instantly and you
can inspect it:

```
/report/html/account.report_invoice/<invoice_id>
```

Check in order:

1. The boxed **Tax Invoice** / **Tax Credit Note** title is back at the top.
2. No standard customer-address block above it, and no leftover gap.
3. The number reads `26AUG_KLRV_00379`, not `26/08_KLRV_00379`.
4. After editing Company Details, `KLOUDIP (PVT) LTD` is back in the header.
5. Print one credit note as well as one invoice — they take different branches
   throughout the template.

If a vertical gap reappears above the title on your layout, tune the single
`margin-top` in `report_styles.css` rather than reinstating `-70px`.
