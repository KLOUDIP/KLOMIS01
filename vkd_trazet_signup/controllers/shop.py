import logging

from odoo.http import request, route

from odoo.addons.website_sale.controllers.cart import Cart
from odoo.addons.website_sale.controllers.main import WebsiteSale

_logger = logging.getLogger(__name__)

SIGNUP_ROUTE = '/trazet-signup'


def _current_user_is_trazet_user():
    user = request.env.user
    return not user._is_public() and user.partner_id.is_trazet_user


class TrazetShopCheckoutGate(WebsiteSale):
    """Block checkout of Trazet products for visitors without a Trazet account.

    Covers every step gated by `_check_cart` (address, checkout, confirm_order,
    payment), regardless of how the product ended up in the cart (combo items
    included).
    """

    def _check_cart(self, order_sudo):
        redirection = super()._check_cart(order_sudo)
        if redirection:
            return redirection

        has_trazet_product = any(
            line.product_id.product_tmpl_id.trazet_product_key
            for line in order_sudo.order_line
        )
        if has_trazet_product and not _current_user_is_trazet_user():
            return request.redirect(SIGNUP_ROUTE)


class TrazetCartGate(Cart):
    """Refuse to add Trazet products to the cart for visitors without a Trazet
    account, and tell the frontend (via `redirect_url`) to send them to the
    sign-up page instead. See static/src/js/cart_service_patch.js for the
    frontend half of this.
    """

    @route()
    def add_to_cart(
        self,
        product_template_id,
        product_id,
        quantity=1.0,
        uom_id=None,
        product_custom_attribute_values=None,
        no_variant_attribute_value_ids=None,
        linked_products=None,
        **kwargs
    ):
        product_ids = [product_id]
        if linked_products:
            # Combo items (and optional products) are only ever passed here, never as the
            # top-level product_id, so a Trazet item bundled inside a combo must be checked
            # explicitly - otherwise it slips through undetected.
            product_ids += [p['product_id'] for p in linked_products if p.get('product_id')]

        products = request.env['product.product'].browse(product_ids).exists()
        has_trazet_product = any(p.product_tmpl_id.trazet_product_key for p in products)

        if has_trazet_product and not _current_user_is_trazet_user():
            order_sudo = request.cart
            return {
                'cart_quantity': order_sudo.cart_quantity if order_sudo else 0,
                'redirect_url': SIGNUP_ROUTE,
                'notification_info': {},
                'quantity': 0,
                'tracking_info': [],
            }

        return super().add_to_cart(
            product_template_id,
            product_id,
            quantity=quantity,
            uom_id=uom_id,
            product_custom_attribute_values=product_custom_attribute_values,
            no_variant_attribute_value_ids=no_variant_attribute_value_ids,
            linked_products=linked_products,
            **kwargs
        )