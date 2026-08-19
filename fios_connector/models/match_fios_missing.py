# -*- coding: utf-8 -*-
# KLOMIS01 v17 -> v19 REMOVAL SHELL - load-only.
from odoo import fields, models
from odoo.exceptions import UserError

_REMOVED = "The FIOS Connector is scheduled for removal and no longer contacts the FIOS API."


class MatchFiosMissing(models.Model):
    _name = 'match.fios.missing'
    _description = 'Match FIOS Missing'
    _inherit = ['mail.thread']
    _rec_name = 'partner_id'

    partner_id = fields.Many2one('res.partner', string='Partner')
    matching_line_ids = fields.One2many('fios.matching.line', 'match_fios_missing_id', string='Fios Matching Lines')
    last_updated = fields.Datetime('Last Updated')

    def get_active_units(self):
        raise UserError(_REMOVED)


class FiosMatchingLine(models.Model):
    _name = "fios.matching.line"
    _description = 'FIOS Matching Line'

    fios_plate_no = fields.Many2one('missing.fleets', string='Fios Plate Number', domain=[('state', '=', 'not_updated')])
    fleet_vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle Number', domain=[('fios_plate_no_updated', '=', False)])
    fios_serial_no = fields.Many2one('missing.serial', string='Fios Serial Number', domain=[('state', '=', 'not_updated')])
    lot_id = fields.Many2one('stock.lot', string='Lot/Serial Number', domain=[('fios_lot_no', '=', False)])
    match_fios_missing_id = fields.Many2one('match.fios.missing', string='Fios Missing')
    plate_matched = fields.Boolean('Plate Matched', help='For UI Purposes')
    serial_matched = fields.Boolean('Serial Matched', help='For UI Purposes')
    removed_from_fios = fields.Boolean('Removed From FIOS')
    different_serial_received_from_fios = fields.Boolean('Different Serial Received from FIOS')

    def form_pop_up(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Open: Fios Matching Lines',
            'res_model': 'fios.matching.line',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def match_vehicle(self):
        raise UserError(_REMOVED)

    def match_serial(self):
        raise UserError(_REMOVED)

    def unmatch_vehicle(self):
        raise UserError(_REMOVED)

    def unmatch_serial(self):
        raise UserError(_REMOVED)

    def remove_matching_line(self):
        raise UserError(_REMOVED)
