from odoo import models, fields, api


class RestrictMenu(models.Model):
    _inherit = 'ir.ui.menu'

    restrict_user_ids = fields.Many2many('res.users')
