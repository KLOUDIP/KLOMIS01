# -*- coding: utf-8 -*-
from odoo import fields, models, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    repair_order_ids = fields.One2many(groups='stock.group_stock_user,sales_team.group_sale_salesman')
    repair_count = fields.Integer(groups='stock.group_stock_user,sales_team.group_sale_salesman')