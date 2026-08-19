# -*- coding: utf-8 -*-
from odoo import models, fields


class SaleSubscriptionPlan(models.Model):
    _inherit = 'sale.subscription.plan'

    is_fios_free_plan = fields.Boolean(
        string='Is FIOS Free Plan?',
        default=False,
        help='If set, this plan is used when auto-creating the free subscription '
             'for a new FIOS customer.',
    )
