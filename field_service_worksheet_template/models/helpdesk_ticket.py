from odoo import models, fields, api, _


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    help_desk_ticket_id = fields.Many2one('project.task', string="Field Service Task")
