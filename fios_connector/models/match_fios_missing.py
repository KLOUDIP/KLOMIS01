# -*- encoding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class MatchFiosMissing(models.Model):
    _name = 'match.fios.missing'
    _description = 'Match FIOS Missing'
    _inherit = 'mail.thread'
    _rec_name = 'partner_id'

    partner_id = fields.Many2one('res.partner', string='Partner')
    matching_line_ids = fields.One2many('fios.matching.line', 'match_fios_missing_id', string='Fios Matching Lines')
    last_updated = fields.Datetime('Last Updated')

    def get_active_units(self):
        """
        Fetch active units for the selected partner
        """
        self.partner_id.get_active_units()

    def unlink(self):
        """Unlink assigned missing serials and plate ids when unlink the record"""
        self.matching_line_ids.unlink()
        return super(MatchFiosMissing, self).unlink()


class FiosMatchingLine(models.Model):
    _name = "fios.matching.line"
    _description = 'FIOS Matching Line'

    fios_plate_no = fields.Many2one('missing.fleets', string='Fios Plate Number', domain=[('state', '=', 'not_updated')])
    fleet_vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle Number', domain=[('fios_plate_no_updated', '=', False)])
    fios_serial_no = fields.Many2one('missing.serial', string='Fios Serial Number', domain=[('state', '=', 'not_updated')])
    lot_id = fields.Many2one('stock.production.lot', string='Lot/Serial Number', domain=[('fios_lot_no', '=', False)])
    match_fios_missing_id = fields.Many2one('match.fios.missing', string='Fios Missing')
    plate_matched = fields.Boolean('Plate Matched', help='For UI Purposes')
    serial_matched = fields.Boolean('Serial Matched', help='For UI Purposes')
    removed_from_fios = fields.Boolean('Removed From FIOS')
    different_serial_received_from_fios = fields.Boolean('Different Serial Received from FIOS')

    def match_vehicle(self):
        """update sync-key in FIOS API"""
        if not self.fleet_vehicle_id:
            raise UserError(_('You need to provide a Fleet Vehicle to match!'))
        # get response from fios API
        active_units_obj = self.env['active.units']
        eid = active_units_obj.get_eid(self.match_fios_missing_id.partner_id.fios_token)
        response = active_units_obj.get_response_from_fios_api(eid)
        # write fleet vehicle number to the FIOS API (sync-key)-------------------------
        item = [item for item in response.get('items') if str(item['id']) == self.fios_plate_no.item_id]
        if len(item) > 1:
            raise ValidationError(_('Multiple item lines found for item_id %s. Cannot find the correct record '
                                    'for update sync-key. Please contact the System Administrator') % self.fios_plate_no.item_id)
        sync_key_rec = active_units_obj.get_sync_key_record(item[0])
        active_units_obj.update_create_sync_key(item[0], sync_key_rec, self.fleet_vehicle_id.license_plate, eid)
        # ---------------------------------------------------------------------
        self.fios_plate_no.update({'state': 'updated'})
        self.fleet_vehicle_id.update({'fios_plate_no_updated': True})
        self.update({'plate_matched': True})

    def match_serial(self):
        """Write fios serial_no to lot, existing in database"""
        if not self.lot_id:
            raise UserError(_('You need to provide a Lot/Serial Number to Match!'))
        self.fios_serial_no.update({'state': 'updated'})
        self.lot_id.update({'fios_lot_no': self.fios_serial_no.unit_serial})
        self.update({'serial_matched': True, 'different_serial_received_from_fios': False})

    def unmatch_vehicle(self):
        for rec in self:
            rec.fleet_vehicle_id.update({'fios_plate_no_updated': False})
            rec.update({'plate_matched': False})
            # unlink active unit record with fleet_id if assigned
            unit_serials = rec.env['active.units'].search([('fleet_vehicle_id', '=', rec.fleet_vehicle_id.id)])
            # set fios_active_unit_available field to false
            unit_serials.mapped('contract_ids').update({'fios_active_unit_available': False})
            # unlink
            unit_serials.unlink()
        return True

    def unmatch_serial(self):
        for rec in self:
            rec.lot_id.update({'fios_lot_no': False})
            rec.update({'serial_matched': False})
            # unlink active unit record with serial if assigned
            unit_serials = rec.env['active.units'].search([('lot_id', '=', rec.lot_id.id)])
            # set fios_active_unit_available field to false
            unit_serials.mapped('contract_ids').update({'fios_active_unit_available': False})
            # unlink
            unit_serials.unlink()
        return True

    def remove_matching_line(self):
        """Remove matching line and open match fios missing form"""
        match_fios_missing_id = self.match_fios_missing_id.id
        if self.removed_from_fios:
            self.unmatch_vehicle()
            self.unmatch_serial()
            # unlink record
            self.unlink()
        try:
            form_view_id = self.env.ref("fios_connector.match_fios_missing_view_form").id
        except Exception as e:
            form_view_id = False
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _("1 Matching line removed!"),
                'next': {
                    'type': 'ir.actions.act_window',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'res_id': match_fios_missing_id,
                    'res_model': 'match.fios.missing',
                    'views': [(form_view_id, 'form')],
                    'target': 'current',
                },
            }
        }

    def unlink(self):
        """Override core method to unmatch serials, vehicles when unlink"""
        self.unmatch_serial()
        self.unmatch_vehicle()
        return super(FiosMatchingLine, self).unlink()
