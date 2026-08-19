
from odoo import _, api, fields, models


class SaleSubscriptionPlan(models.Model):
    _inherit = "sale.subscription.plan"

    is_free_plan = fields.Boolean(
        'Is Free Plan?',
        default=False,
        help='If set, this plan will be used for creating free subscriptions for new customers'
    )