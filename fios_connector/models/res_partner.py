# -*- encoding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    active_unit_ids = fields.One2many('active.units', 'partner_id', string='Active Units')
    fios_token = fields.Char(string='FIOS Token', help='Partner token for the FIOS Account')

    def get_active_units(self):
        if not self.fios_token:
            raise UserError(_('No FIOS Token found for the current driver!'))
        else:
            eid = self.env['active.units'].get_eid(self.fios_token)
            response = self.env['active.units'].get_response_from_fios_api(eid)
            self.env['active.units'].get_active_units(self, response, eid)
            return True

    def scheduler_for_fios(self):
        for rec in self.search([('type', '=', 'invoice'), ('fios_token', '!=', False)]):
            eid = rec.env['active.units'].get_eid(rec.fios_token)
            response = rec.env['active.units'].get_response_from_fios_api(eid)
            rec.env['active.units'].get_active_units(rec, response, eid)
