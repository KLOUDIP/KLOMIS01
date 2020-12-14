# -*- coding: utf-8 -*-
from odoo import api, models, _, fields

class SaleOrder(models.Model):
    _inherit = "sale.order"

    project_id = fields.Many2one("project.project", string="Task Type")

    def _prepare_invoice(self):
        inv = super(SaleOrder, self)._prepare_invoice()
        inv.update({"project_id": self.project_id})
        return inv

