# -*- coding: utf-8 -*-
from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    repair_order_ids = fields.One2many(groups='stock.group_stock_user,sales_team.group_sale_salesman')
    repair_count = fields.Integer(groups='stock.group_stock_user,sales_team.group_sale_salesman')
    device_repair_order_id = fields.Many2one('repair.order', string="Repair Order")

    def action_show_device_repair(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "repair.order",
            "views": [[False, "form"]],
            "res_id": self.device_repair_order_id.id,
        }