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