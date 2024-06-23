# -*- coding: utf-8 -*-

from odoo import api, models

from odoo.tools import format_amount


class SaleSubscriptionPricing(models.Model):
    _inherit = 'sale.subscription.pricing'

    @api.depends_context('sale_recurring')
    def _compute_display_name(self):
        if self.env.context.get('sale_recurring', True):
            for record in self:
                record.display_name = f'{record.name}: {format_amount(record.env, record.price, record.currency_id)}'
        else:
            return super()._compute_display_name()
