# -*- coding: utf-8 -*-
from odoo import models, fields


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    coordinator_assigned_ids = fields.One2many("coordinator.unit.line", "employee_id", string="Unit Count")

class HrEmployeePublic(models.Model):
    _inherit = "hr.employee.public"

    coordinator_assigned_ids = fields.One2many(related="employee_id.coordinator_assigned_ids")
    is_logged_in_user = fields.Boolean(string="LoggedIn Employee", compute="_check_loggedin_user")

    def _check_loggedin_user(self):
        for rec in self:
            is_logged_in_user = False
            if rec.user_id.id == self.env.user.id:
                is_logged_in_user = True
            if self.user_has_groups('base.group_system'):
                is_logged_in_user = True
            rec.is_logged_in_user = is_logged_in_user