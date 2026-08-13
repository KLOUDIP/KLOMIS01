from odoo import models, fields, api, _


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    help_desk_ticket_id = fields.Many2one('project.task', string="Field Service Task")
    partner_mobile = fields.Char(
        string='Mobile',
        compute='_compute_partner_mobile',
        inverse='_inverse_partner_mobile',
        readonly=False,
    )

    def _compute_partner_mobile(self):
        for rec in self:
            rec.partner_mobile = rec.partner_id.phone if rec.partner_id else False

    def _inverse_partner_mobile(self):
        for rec in self:
            if rec.partner_id:
                rec.partner_id.phone = rec.partner_mobile