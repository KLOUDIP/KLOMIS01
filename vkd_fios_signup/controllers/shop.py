# -*- coding: utf-8 -*-
import logging

from odoo.http import request, route

from odoo.addons.website_sale.controllers.cart import Cart
from odoo.addons.website_sale.controllers.combo_configurator import (
    WebsiteSaleComboConfiguratorController,
)
from odoo.addons.website_sale.controllers.main import WebsiteSale

_logger = logging.getLogger(__name__)

SIGNUP_ROUTE = '/fios-signup'


def _related_templates(tmpl):
    """`tmpl` together with the templates offered inside its combo choices.

    A `combo` product is frequently left untagged while the FIOS markers sit on
    the items it bundles (or the other way round). Looking at both ends means a
    bundle gates on the strength of whatever it actually sells. Sudo because the
    choices of a combo need not be published for the combo itself to be.
    """
    tmpl_sudo = tmpl.sudo()
    return tmpl_sudo | tmpl_sudo.combo_ids.combo_item_ids.product_id.product_tmpl_id


def _is_fios_template(tmpl):
    return any(t.fios_tier_id or t.fios_service for t in _related_templates(tmpl))


def _is_fios_product(product):
    return _is_fios_template(product.product_tmpl_id)


def _current_user_registered():
    user = request.env.user
    return not user._is_public() and user.partner_id.is_fios_user


def _fios_tiers(products):
    templates = products.product_tmpl_id.sudo()
    templates |= templates.combo_ids.combo_item_ids.product_id.product_tmpl_id
    return templates.fios_tier_id


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


class FiosComboConfiguratorGate(WebsiteSaleComboConfiguratorController):
    """Gate the combo configurator, which runs *before* the cart.

    Adding a `combo` product from the shop calls
    /website_sale/combo_configurator/get_data first and only posts to
    /shop/cart/add once the visitor has picked an item per choice. Gating the
    cart alone would therefore make an unregistered visitor configure the whole
    bundle before being told to sign up. Returning `redirect_url` here is the
    same contract FiosCartGate uses; static/src/js/cart_service_patch.js acts
    on it for both routes.
    """

    @route()
    def website_sale_combo_configurator_get_data(self, *args, **kwargs):
        tmpl_id = kwargs.get('product_tmpl_id') or (args[0] if args else None)
        tmpl = request.env['product.template'].browse(int(tmpl_id)).exists() if tmpl_id else None
        if tmpl and _is_fios_template(tmpl) and not _current_user_registered():
            return {'redirect_url': SIGNUP_ROUTE}
        return super().website_sale_combo_configurator_get_data(*args, **kwargs)


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
