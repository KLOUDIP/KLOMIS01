# -*- coding: utf-8 -*-
from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        epc = self.order_line.filtered(lambda x: x.product_id.is_epc == True)
        for order in self:
            if order.partner_id.type == 'invoice':
                order.create_epc_transaction(epc)
        return res

    def create_epc_transaction(self, epc):
        data = {
            'date': self.date_order,
            'amount': epc.product_uom_qty,
            'type': 'top_up',
            'state': 'confirm',
            'order_id': self.id,
        }
        self.partner_id.write({
            'transaction_ids': [(0, 0, data)],
            'last_updated_epc_amount': epc.product_uom_qty
        })


