# -*- coding: utf-8 -*-
import logging

from odoo.http import request, route

from odoo.addons.website_sale.controllers.cart import Cart
from odoo.addons.website_sale.controllers.main import WebsiteSale

_logger = logging.getLogger(__name__)

SIGNUP_ROUTE = '/fios-signup'


def _is_fios_product(product):
    tmpl = product.product_tmpl_id
    return bool(tmpl.fios_tier_id or tmpl.fios_service)


def _current_user_registered():
    user = request.env.user
    return not user._is_public() and user.partner_id.is_fios_user


def _fios_tiers(products):
    return products.mapped('product_tmpl_id.fios_tier_id')


def _tier_conflict(partner, tiers):
    ids = set(tiers.ids)
    if partner and partner.fios_tier_id:
        ids.add(partner.fios_tier_id.id)
    return len(ids) > 1


class FiosShopCheckoutGate(WebsiteSale):

    def _check_cart(self, order_sudo):
        redirection = super()._check_cart(order_sudo)
        if redirection:
            return redirection

        fios_products = order_sudo.order_line.mapped('product_id').filtered(_is_fios_product)
        if not fios_products:
            return
        if not _current_user_registered():
            return request.redirect(SIGNUP_ROUTE)
        if _tier_conflict(request.env.user.partner_id, _fios_tiers(fios_products)):
            return request.redirect('/shop/cart?error=fios_tier')


class FiosCartGate(Cart):

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
            # Combo/optional items are only ever passed here, never as the
            # top-level product_id, so a FIOS item bundled inside a combo must be
            # checked explicitly - otherwise it slips through undetected.
            product_ids += [p['product_id'] for p in linked_products if p.get('product_id')]

        products = request.env['product.product'].browse(product_ids).exists()
        fios_products = products.filtered(_is_fios_product)

        if fios_products:
            order_sudo = request.cart
            # Not registered yet -> send to sign-up.
            if not _current_user_registered():
                return {
                    'cart_quantity': order_sudo.cart_quantity if order_sudo else 0,
                    'redirect_url': SIGNUP_ROUTE,
                    'notification_info': {},
                    'quantity': 0,
                    'tracking_info': [],
                }
            # Mutual exclusion: block a tier that conflicts with the customer's
            # committed tier or with FIOS products already in the cart.
            partner = request.env.user.partner_id
            cart_fios = order_sudo.order_line.mapped('product_id').filtered(_is_fios_product) if order_sudo else products.browse()
            tiers = _fios_tiers(fios_products) | _fios_tiers(cart_fios)
            if _tier_conflict(partner, tiers):
                return {
                    'cart_quantity': order_sudo.cart_quantity if order_sudo else 0,
                    'redirect_url': '/shop/cart?error=fios_tier',
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