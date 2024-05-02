# -*- coding: utf-8 -*-
from odoo import fields, models, Command


class SaleOrder(models.Model):
    _inherit = "sale.order"

    coordinator_id = fields.Many2one("res.users", string="Assigned To", tracking=True)