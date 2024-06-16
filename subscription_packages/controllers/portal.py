# -*- coding: utf-8 -*-

from odoo import SUPERUSER_ID, _

from odoo.http import request, route
from odoo.tools import format_amount

from odoo.addons.sale.controllers import portal


class CustomerPortal(portal.CustomerPortal):

    @route(['/portal/update/sale/subscription/package'], type='json', auth="public", website=True)
    def portal_update_sale_subscription_package(self, subscription_pkg_id, sale_id, **kwargs):
        """
        @public - update the sale subscription package to the sale order
        """
        sale_id = request.env['sale.order'].with_user(SUPERUSER_ID).browse(int(sale_id))
        subscription_pkg_id = request.env['sale.subscription.plan'].with_user(SUPERUSER_ID).browse(
            int(subscription_pkg_id))
        sale_id.update({
            'custom_plan_id': subscription_pkg_id.id
        })
        # Update the sale order fields
        sale_id._onchange_custom_plan_id()
        for rec in sale_id.sale_order_recurring_ids:
            rec._compute_amount()
        # Add log note
        sale_id.with_user(request.env.user.id).message_post(body=f"Subscription plan changed by user {request.env.user.partner_id.name}", subject="Subscription plan changed")
        return _(
            f'Sale order: {sale_id.name}. Updated successfully using subscription package {subscription_pkg_id.display_name}.')

    @route(['/get/sale/subscription/package/price'], type='json', auth="public", website=True)
    def portal_get_sale_subscription_package_price(self, sale_id, subscription_package_id, product_id, recurring_line_id, **kwargs):
        """
        @public - get the package pricing with price-list
        """
        subscription_plan_id = request.env['sale.subscription.plan'].with_user(SUPERUSER_ID).browse(
            int(subscription_package_id))
        product_id = request.env['product.product'].with_user(SUPERUSER_ID).browse(int(product_id))
        plan_line_id = subscription_plan_id.product_subscription_pricing_ids.filtered(lambda x: x.product_template_id.id == product_id.product_tmpl_id.id)
        pricelist_id = plan_line_id.pricelist_id
        recurring_line_id = request.env['sale.order.recurring'].with_user(SUPERUSER_ID).browse(int(recurring_line_id))

        def _get_price(product_qty):
            """
            @nested - get the pricing with price-list
            return: type - Tuple (format_amount, unit_price, price_subtotal)
            """
            # Compute product price
            product_price = pricelist_id._get_product_price(product_id, product_qty or 1.0, currency=pricelist_id.currency_id)
            product_price_formatted = format_amount(request.env, product_price, pricelist_id.currency_id) if pricelist_id else '0'
            # Compute price subtotal
            tax_results = request.env['account.tax']._compute_taxes([
                recurring_line_id._convert_to_tax_base_line_dict()
            ])
            totals = list(tax_results['totals'].values())[0]
            price_subtotal = totals['amount_untaxed']
            price_subtotal_formatted = format_amount(request.env, price_subtotal, pricelist_id.currency_id) if pricelist_id else '0'
            return tuple([product_price_formatted, product_price, price_subtotal_formatted, price_subtotal, bool(pricelist_id)])

        return _get_price(recurring_line_id.quantity)
