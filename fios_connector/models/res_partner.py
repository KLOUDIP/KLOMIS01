# -*- encoding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    active_unit_ids = fields.One2many('active.units', 'partner_id', string='Active Units')
    fios_token = fields.Char(string='FIOS Token', help='Partner token for the FIOS Account')
    fios_fleet_count = fields.Integer(string='FIOS Fleet Count', compute='_compute_fios_fleets')

    def _compute_fios_fleets(self):
        """Compute matching lines that belongs to current partner"""
        matching_record_ids = self.env['match.fios.missing'].search([('partner_id', '=', self.id)]).mapped('matching_line_ids')
        self.update({'fios_fleet_count': len(matching_record_ids)})

    def action_view_matching_lines(self):
        """View matching lines"""
        matching_record_ids = self.env['match.fios.missing'].search([('partner_id', '=', self.id)]).mapped('matching_line_ids')
        return_dict = {
            'name': _('FIOS Fleets'),
            'res_model': 'fios.matching.line',
            'type': 'ir.actions.act_window',
            'target': 'current',
        }
        if len(matching_record_ids) > 1:
            return_dict.update({
                'view_mode': 'tree',
                'view_id': self.env.ref('fios_connector.fios_matching_line_view_tree').id,
                'domain': [('id', 'in', matching_record_ids.ids)]
            })
        else:
            return_dict.update({
                'view_mode': 'form',
                'view_id': self.env.ref('fios_connector.fios_matching_line_view_form').id,
                'res_id': matching_record_ids.id,
            })
        return return_dict

    def get_active_units(self):
        """Get Active units for the current partner"""
        if not self.fios_token:
            raise UserError(_('No FIOS Token found for the current driver!'))
        elif self.subscription_count == 0:
            raise ValidationError(_('Partner doesn\'t have any subscriptions. '
                                    'Active units not available for partners without subscription.'))
        elif self.type != 'invoice':
            raise ValidationError(_('Token can be added only to the billing contacts'))

        else:
            eid = self.env['active.units'].get_eid(self.fios_token)
            response = self.env['active.units'].get_response_from_fios_api(eid)
            self.env['active.units'].get_active_units(self, response, eid)
            return True

    def scheduler_for_fios(self):
        """Schedule action for get active units for the partners"""
        for rec in self.search([('type', '=', 'invoice'), ('fios_token', '!=', False), ('subscription_count', '>', 0)]):
            eid = rec.env['active.units'].get_eid(rec.fios_token)
            response = rec.env['active.units'].get_response_from_fios_api(eid)
            rec.env['active.units'].get_active_units(rec, response, eid)
