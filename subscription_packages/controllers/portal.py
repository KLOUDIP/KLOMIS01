# -*- coding: utf-8 -*-

from odoo.exceptions import AccessError, MissingError
from odoo.http import request, route

from odoo.addons.sale.controllers import portal


class CustomerPortal(portal.CustomerPortal):

    @route(
        ['/portal/update/sale/subscription/package'],
        type='jsonrpc', auth="public", website=True,
    )
    def portal_update_sale_subscription_package(
        self, subscription_pkg_id, sale_id, access_token=None, **kwargs
    ):
        """Set the subscription plan chosen by the customer on the quotation.

        :param int sale_id: `sale.order` id
        :param int subscription_pkg_id: `sale.subscription.plan` id
        :param str access_token: portal access token of the specified order
        """
        try:
            order_sudo = self._document_check_access(
                'sale.order', int(sale_id), access_token=access_token)
        except (AccessError, MissingError):
            return {'error': request.env._("You are not allowed to update this quotation.")}

        if not order_sudo._can_be_edited_on_portal():
            return {'error': request.env._("You cannot change the plan of a confirmed order.")}

        plan_sudo = request.env['sale.subscription.plan'].sudo().browse(
            int(subscription_pkg_id)).exists()
        if not plan_sudo:
            return {'error': request.env._("This subscription plan does not exist.")}

        order_sudo.custom_plan_id = plan_sudo
        # Re-apply the plan pricing on the recurring lines. The amounts are
        # stored computed fields and refresh on their own once price_unit
        # changes, so there is no need to trigger _compute_amount by hand.
        order_sudo._onchange_custom_plan_id()

        # Posted as sudo: a public portal visitor has no write access on the order.
        order_sudo.message_post(
            body=request.env._(
                "Subscription plan changed by %(user)s",
                user=request.env.user.partner_id.name,
            ),
            subject=request.env._("Subscription plan changed"),
        )

        return {
            'message': request.env._(
                "Sale order %(order)s updated successfully using subscription package %(plan)s.",
                order=order_sudo.name,
                plan=plan_sudo.display_name,
            ),
        }
