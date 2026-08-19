# -*- coding: utf-8 -*-
# KLOMIS01 v17 -> v19 REMOVAL SHELL - load-only.
from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    coordinator_id = fields.Many2one("res.users", string="Assigned To", tracking=True)
