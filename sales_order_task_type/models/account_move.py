# -*- coding: utf-8 -*-
from odoo import fields, models

class AccountMove(models.Model):
    _inherit = 'account.move'

    task_type_id = fields.Many2one("project.project", string="Task Type")