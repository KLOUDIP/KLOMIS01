# -*- coding: utf-8 -*-
from odoo import models, fields


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    coordinator_assigned_ids = fields.One2many("coordinator.unit.line", "employee_id", string="Unit Count")