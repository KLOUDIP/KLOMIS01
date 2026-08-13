# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class HrContract(models.Model):
    _inherit = 'hr.contract'

    deduction_basic = fields.Monetary(string="Deduction Basic")
    deduction_reimb = fields.Monetary(string="Deduction Reimb")
    deduction_unpaid_leave = fields.Monetary(string="Deduction Unpaid Leave")
    phone_bill_excess = fields.Monetary(string="Phone Bill Excess")
    reimb_exp = fields.Monetary(string="Reimb-Exp")
    reimb_trav = fields.Monetary(string="Reimb-Trav")
    br_allowance_one = fields.Monetary(string="BR-Allowance-1")
    br_allowance_two = fields.Monetary(string="BR-Allowance-2")
    paye = fields.Monetary(string="PAYE")