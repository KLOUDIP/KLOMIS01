# -*- coding: utf-8 -*-
from odoo import fields, models, api

class Picking(models.Model):
    _inherit = "stock.picking"

    task_type_id = fields.Many2one("project.project", related='sale_id.task_type_id', string="Task Type")
