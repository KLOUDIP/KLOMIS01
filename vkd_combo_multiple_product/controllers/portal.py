import datetime
import werkzeug
from collections import OrderedDict
from dateutil.relativedelta import relativedelta
from math import ceil
from werkzeug.urls import url_encode

from odoo import Command, fields, http, _
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.http import request
from odoo.tools import format_date, str2bool

from odoo.addons.sale.controllers import portal as payment_portal
from odoo.addons.payment import utils as payment_utils
from odoo.addons.portal.controllers.portal import pager as portal_pager
from odoo.addons.sale.controllers import portal as sale_portal
from odoo.addons.sale_subscription.models.sale_order import SUBSCRIPTION_PROGRESS_STATE, SUBSCRIPTION_CLOSED_STATE


class CustomerPortal(payment_portal.PaymentPortal):


    @http.route(['/my/subscriptions/<int:order_id>/change_plan'], type='http', methods=["POST"], auth="public",
                website=True)
    def change_plan(self, order_id, access_token=None, **kw):
        order_sudo, redirection = self._get_subscription(access_token, order_id)
        if redirection:
            return redirection
        if order_sudo.plan_id.related_plan_id and order_sudo._can_be_edited_on_portal():
            if new_plan := request.env['sale.subscription.plan'].browse(int(kw.get('plan_id'))):
                old_plan = order_sudo.plan_id
                order_sudo.plan_id = new_plan
                # After plan change, update prices for combo lines
                if old_plan != new_plan:
                    order_sudo.order_line.filtered(lambda l: l.combo_item_id).with_context(
                        force_price_recalculation=True
                    )._compute_price_unit()
        return request.redirect(order_sudo.get_portal_url())
