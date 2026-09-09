/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";

/**
 * Click-time sign-up gate.
 *
 * cart_service_patch.js acts on a `redirect_url` that the server puts in the
 * response of a cart route. That is the authoritative gate, but it only fires
 * once website_sale has actually made that call and read the answer, so every
 * step in between is a way for the prompt to disappear:
 *
 *  - `CartService.add` branches on `isCombo`, `should_show_product_configurator`
 *    and `isBuyNow`, and each branch calls a different route first;
 *  - a failure anywhere in `/shop/cart/add` (a company-consistency error while
 *    creating the cart, for instance) rejects the RPC before any of our fields
 *    are looked at, and the click then does nothing at all - which is exactly
 *    what an unregistered visitor reports as "the sign-up form never came up".
 *
 * So the decision is taken here instead, on the click itself, which is the one
 * point every add-to-cart path goes through. The set of gated products on the
 * page is fetched once on load, making the common case a synchronous decision;
 * anything not covered by that prefetch falls back to a single per-click check.
 */

const SIGNUP_ROUTE = "/fios-signup";
const CHECK_ROUTE = "/fios-signup/gate/check";

const ADD_TO_CART_SELECTOR = [
    "#add_to_cart", // product page
    ".o_we_buy_now", // product page, "Buy now"
    ".o_wsale_product_btn .a-submit", // shop grid tile
    ".s_add_to_cart_btn", // "Add to cart" snippet
    ".o_carousel_product_card .js_add_cart", // products carousel / recently viewed
].join(", ");

/** Template ids already answered for, and the subset of them that is gated. */
const resolved = new Set();
const gated = new Set();

/** Buttons whose click we re-dispatched, so we let that second click through. */
const passingThrough = new WeakSet();

function toId(value) {
    const id = parseInt(value);
    return isNaN(id) ? null : id;
}

/**
 * The product template behind an add-to-cart control. The shop grid and the
 * product page carry it in a hidden input inside the product form; the snippets
 * carry it on the element's own dataset instead.
 */
function templateIdOf(el) {
    const carrier = el.closest("[data-product-template-id]");
    if (carrier) {
        return toId(carrier.dataset.productTemplateId);
    }
    const scope = el.closest("form") || el.closest(".js_product") || el.closest(".oe_product");
    return toId(scope?.querySelector('input[type="hidden"][name="product_template_id"]')?.value);
}

function templateIdsOnPage() {
    const fromForms = [
        ...document.querySelectorAll('input[type="hidden"][name="product_template_id"]'),
    ].map((input) => input.value);
    const fromDatasets = [...document.querySelectorAll("[data-product-template-id]")].map(
        (el) => el.dataset.productTemplateId
    );
    return [...new Set([...fromForms, ...fromDatasets].map(toId).filter((id) => id !== null))];
}

/**
 * Ask the server which of `ids` are FIOS products the current visitor may not
 * buy yet, and remember the answer for both outcomes.
 *
 * A failed check resolves nothing: the next click asks again rather than
 * caching "not gated", so a transient error cannot quietly disable the gate.
 */
async function resolveTemplates(ids) {
    const unknown = ids.filter((id) => !resolved.has(id));
    if (!unknown.length) {
        return;
    }
    const data = await rpc(CHECK_ROUTE, { product_template_ids: unknown });
    for (const id of unknown) {
        resolved.add(id);
    }
    for (const id of data?.gated_template_ids || []) {
        gated.add(id);
    }
}

function redirectToSignup() {
    window.location.href = SIGNUP_ROUTE;
}

function block(ev) {
    ev.preventDefault();
    ev.stopPropagation();
    ev.stopImmediatePropagation();
}

async function onAddToCartClick(ev) {
    const button = ev.target?.closest?.(ADD_TO_CART_SELECTOR);
    if (!button) {
        return;
    }
    if (passingThrough.has(button)) {
        // Our own re-dispatch: let website_sale handle it normally.
        return;
    }
    const templateId = templateIdOf(button);
    if (!templateId) {
        return;
    }

    if (resolved.has(templateId)) {
        if (gated.has(templateId)) {
            block(ev);
            redirectToSignup();
        }
        return;
    }

    // Not answered yet (the prefetch has not landed, or this tile was injected
    // afterwards). Hold the click, ask, then either redirect or replay it.
    block(ev);
    try {
        await resolveTemplates([templateId]);
    } catch {
        // Server unreachable: fall through and let website_sale try, whose own
        // server-side gate is still in place.
    }
    if (gated.has(templateId)) {
        redirectToSignup();
        return;
    }
    passingThrough.add(button);
    button.click();
    setTimeout(() => passingThrough.delete(button), 0);
}

function prefetch() {
    const ids = templateIdsOnPage();
    if (ids.length) {
        resolveTemplates(ids).catch(() => {});
    }
}

// Capture phase on the document: website_sale binds its own handler by
// delegation on `.oe_website_sale`, which is below this one and in the bubble
// phase, so a gated click never reaches it.
document.addEventListener("click", onAddToCartClick, true);

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", prefetch, { once: true });
} else {
    prefetch();
}
