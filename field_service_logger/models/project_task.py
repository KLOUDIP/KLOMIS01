from odoo import models, fields, api, _

class ProjectTask(models.Model):
    _inherit = "project.task"

    planned_date_begin = fields.Datetime(tracking=True)
    partner_id = fields.Many2one(tracking=True)
    partner_mobile = fields.Char(tracking=True)
    partner_phone = fields.Char(tracking=True)
