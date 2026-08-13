# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SaleOrderTemplateRecurring(models.Model):
    _name = "sale.order.template.recurring"
    _inherit = 'sale.order.template.option'
    _description = 'Sale Order Template Recurring'

    def _prepare_recurring_line_values(self):
        """
        @private - Give the values to create the corresponding option line.

        :return: `sale.order.option` create values
        :rtype: dict
        """
        self.ensure_one()
        return {
            'name': self.name,
            'product_id': self.product_id.id,
            'quantity': self.quantity,
            'uom_id': self.uom_id.id,
            'tax_ids': [(4, x.id) for x in self.product_id.taxes_id]
        }
