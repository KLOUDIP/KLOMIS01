/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { CartService } from "@website_sale/js/cart_service";
import { browser } from "@web/core/browser/browser";
import { session } from "@web/session";

patch(CartService.prototype, {
    /**
     * The server responds with `redirect_url` instead of the usual cart-add
     * payload when a FIOS product was blocked from being added because the
     * visitor doesn't have a FIOS account yet (see controllers/shop.py:
     * FiosCartGate.add_to_cart). Checked right after the RPC call, before the
     * "Buy Now" branch below, since that branch redirects to /shop/cart on its
     * own and never reaches `_showCartNotification`.
     *
     * The redirect handling is generic (it honours whatever `redirect_url` the
     * server returns), so this stays correct even if the Trazet signup module's
     * equivalent patch is also installed.
     */
    async _makeRequest({
        productTemplateId,
        productId,
        quantity,
        uomId = undefined,
        productCustomAttributeValues = [],
        noVariantAttributeValues = [],
        shouldRedirectToCart = false,
        ...rest
    }) {
        const data = await this.rpc('/shop/cart/add', {
            product_template_id: productTemplateId,
            product_id: productId,
            quantity: quantity,
            uom_id: uomId,
            product_custom_attribute_values: productCustomAttributeValues,
            no_variant_attribute_value_ids: noVariantAttributeValues,
            ...rest
        });

        if (data.redirect_url) {
            window.location.href = data.redirect_url;
            return 0;
        }

        if (shouldRedirectToCart || session.add_to_cart_action === 'go_to_cart') {
            window.location = '/shop/cart';
            return data.quantity;
        }
        if (data.cart_quantity && (
            data.cart_quantity !== browser.sessionStorage.getItem('website_sale_cart_quantity')
        )) {
            this._updateCartIcon(data.cart_quantity);
        }
        this._showCartNotification(data.notification_info);
        if (data.quantity) {
            this._trackProducts(data.tracking_info);
        }
        return data.quantity;
    },
});