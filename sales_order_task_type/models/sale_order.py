# -*- coding: utf-8 -*-
from odoo import api, models, _, fields

class SaleOrder(models.Model):
    _inherit = "sale.order"

    task_type_id = fields.Many2one("project.project", string="Task Type")

    def _prepare_invoice(self):
        inv = super(SaleOrder, self)._prepare_invoice()
        inv.update({"task_type_id": self.task_type_id})
        return inv