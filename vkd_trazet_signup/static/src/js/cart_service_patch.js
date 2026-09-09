/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
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
    '/website_sale/product_configurator/get_values',
]);

/**
 * Returned in place of the refused payload. It never settles on purpose: the
 * browser is already navigating away, and letting the caller resume would run
 * it against a response that has none of the fields it destructures.
 */
const NAVIGATING_AWAY = new Promise(() => {});

/**
 * Marker set on an error once one of these wrappers has reported it. If the
 * FIOS sign-up module is installed too its wrapper nests with this one, and
 * the same rejection would otherwise raise two identical dialogs.
 */
const REPORTED = "_vkdCartFailureReported";

patch(CartService.prototype, {
    /**
     * Wrap `this.rpc` rather than overriding `_makeRequest`/`add`.
     *
     * `setup` assigns `this.rpc = rpc` expressly so it can be swapped out, and
     * wrapping it there covers every gated route from one seam without copying
     * any of the upstream cart logic (which would silently drift the next time
     * website_sale changes). If the FIOS sign-up module is installed too, its
     * identical wrapper simply nests with this one - whichever runs first
     * redirects, and the other never resumes.
     */
    setup() {
        const api = super.setup(...arguments);
        const rpc = this.rpc;
        this.rpc = async (route, params, settings) => {
            let data;
            try {
                data = await rpc(route, params, settings);
            } catch (error) {
                if (GATED_ROUTES.has(route)) {
                    this._trazetReportCartFailure(route, error);
                }
                throw error;
            }
            if (GATED_ROUTES.has(route) && data?.redirect_url) {
                window.location.href = data.redirect_url;
                return NAVIGATING_AWAY;
            }
            return data;
        };
        return api;
    },

    /**
     * Tell the visitor a cart call failed.
     *
     * website_sale reports nothing when one of these routes rejects: the
     * click simply does nothing, which looks exactly like a sign-up gate that
     * never fired, and sends the investigation to the wrong half of the
     * system. A server-side refusal (a company-consistency error while
     * creating the cart, say) is a fault of the shop's configuration rather
     * than anything the shopper did, so the dialog stays generic and the
     * server's own wording goes to the console for whoever is debugging.
     */
    _trazetReportCartFailure(route, error) {
        if (error?.[REPORTED]) {
            return;
        }
        try {
            error[REPORTED] = true;
        } catch {
            // Frozen or non-object rejection: a duplicate dialog is better
            // than swallowing the report entirely.
        }
        // eslint-disable-next-line no-console
        console.error(
            `[vkd_trazet_signup] ${route} failed:`,
            error?.data?.message || error?.message || error
        );
        this.dialog?.add(AlertDialog, {
            title: _t("Add to cart"),
            body: _t(
                "Sorry, this product could not be added to your cart. Please try again, "
                + "or contact us if the problem persists."
            ),
        });
    },
});
