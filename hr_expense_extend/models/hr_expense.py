# -*- coding: utf-8 -*-

from odoo import api, fields, Command, models, _


class HrExpense(models.Model):

    _inherit = "hr.expense"

    def action_open_expense_form(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "hr.expense",
            "views": [[False, "form"]],
            "res_id": self.id,
        }