from odoo import models, fields, api, _

class Task(models.Model):
    _inherit = "project.task"

    planned_date_begin = fields.Datetime(track_visibility='onchange')
    partner_id = fields.Many2one(track_visibility='onchange')
    partner_mobile = fields.Char(track_visibility='onchange')
    partner_phone = fields.Char(track_visibility='onchange')
