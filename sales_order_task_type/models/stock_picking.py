# -*- coding: utf-8 -*-
from odoo import fields, models, api

class Picking(models.Model):
    _inherit = "stock.picking"

    project_id = fields.Many2one("project.project", related='sale_id.project_id', string="Task Type")

    # @api.model
    # def create(self, values):
    #     return super(Picking, self).create(values)
