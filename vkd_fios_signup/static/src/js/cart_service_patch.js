/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { CartService } from "@website_sale/js/cart_service";

/**
 * Routes whose response may carry a `redirect_url` instead of the payload the
 * caller expects, because the server refused the operation and wants the
 * visitor sent elsewhere (see controllers/shop.py).
 *
 * `/website_sale/combo_configurator/get_data` matters as much as the cart
 * route: for a `combo` product it is the *first* call the browser makes, so a
 * gate that only covered `/shop/cart/add` would let an unregistered visitor
 * configure the whole bundle before being bounced to the sign-up page.
 */
const GATED_ROUTES = new Set([
    '/shop/cart/add',
    '/website_sale/combo_configurator/get_data',
]);

/**
 * Returned in place of the refused payload. It never settles on purpose: the
 * browser is already navigating away, and letting the caller resume would run
 * it against a response that has none of the fields it destructures.
 */
const NAVIGATING_AWAY = new Promise(() => {});

patch(CartService.prototype, {
    /**
     * Wrap `this.rpc` rather than overriding `_makeRequest`/`add`.
     *
     * `setup` assigns `this.rpc = rpc` expressly so it can be swapped out, and
     * wrapping it there covers every gated route from one seam without copying
     * any of the upstream cart logic (which would silently drift the next time
     * website_sale changes). If the Trazet sign-up module is installed too, its
     * identical wrapper simply nests with this one - whichever runs first
     * redirects, and the other never resumes.
     */
    setup() {
        const api = super.setup(...arguments);
        const rpc = this.rpc;
        this.rpc = async (route, params, settings) => {
            const data = await rpc(route, params, settings);
            if (GATED_ROUTES.has(route) && data?.redirect_url) {
                window.location.href = data.redirect_url;
                return NAVIGATING_AWAY;
            }
            return data;
        };
        return api;
    },
});
