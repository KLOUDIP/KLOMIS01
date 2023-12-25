# -*- encoding: utf-8 -*-

from odoo import api, fields, models


class StockProductionLot(models.Model):
    _inherit = 'stock.lot'

    is_manager = fields.Boolean(string="Is Manager", compute="check_user_group")

    @api.depends_context('uid')
    def check_user_group(self):
        is_manager = self.env.user.has_group('stock.group_stock_manager')
        for rec in self:
            rec.is_manager = is_manager
