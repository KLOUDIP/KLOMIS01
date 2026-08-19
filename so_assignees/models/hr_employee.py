# -*- coding: utf-8 -*-
# KLOMIS01 v17 -> v19 REMOVAL SHELL - load-only.
from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    coordinator_assigned_ids = fields.One2many(
        "coordinator.unit.line", "employee_id", string="Unit Count")


class HrEmployeePublic(models.Model):
    _inherit = "hr.employee.public"

    coordinator_assigned_ids = fields.One2many(related="employee_id.coordinator_assigned_ids")
    is_logged_in_user = fields.Boolean(string="LoggedIn Employee", compute="_check_loggedin_user")

    def _check_loggedin_user(self):
        # v17 called self.user_has_groups(), removed from the ORM in v17/v18.
        is_admin = self.env.user.has_group('base.group_system')
        for rec in self:
            rec.is_logged_in_user = is_admin or rec.user_id.id == self.env.user.id
