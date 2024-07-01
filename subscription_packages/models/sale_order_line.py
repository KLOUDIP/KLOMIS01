# -*- coding: utf-8 -*-
from odoo import api, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.depends('order_id.rental_start_date', 'order_id.rental_return_date', 'is_rental')
    def _compute_name(self):
        subs_product_ids = self.order_id.sale_order_recurring_ids.mapped('product_id').ids
        recurring_lines = self.filtered(lambda x: x.recurring_invoice and x.product_id.id in subs_product_ids)
        if recurring_lines:
            super(SaleOrderLine, self - recurring_lines)._compute_name()
        else:
            super()._compute_name()
