# -*- coding: utf-8 -*-
# KLOMIS01 v17 -> v19 REMOVAL SHELL - load-only.
import logging

from odoo import fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_REMOVED = "The FIOS Connector is scheduled for removal and no longer contacts the FIOS API."


class ActiveUnits(models.Model):
    _name = 'active.units'
    _description = 'Active Units'
    _rec_name = 'plate_no'

    unit_serial = fields.Char(string='Unit Serial')
    plate_no = fields.Char(string='Plate Number')
    contract_ids = fields.Many2many('fleet.vehicle.log.contract', 'fleet_contracts', string='Fleet Contracts')
    partner_id = fields.Many2one('res.partner', string='Partner')
    contracts_empty = fields.Boolean(string='Contracts Empty', help='For UI Purposes')
    fleet_vehicle_id = fields.Many2one('fleet.vehicle', string='Fleet Vehicle')
    sync_key = fields.Char(
        string='Sync-Key', related='fleet_vehicle_id.license_plate',
        help='FIOS API Sync-Key (Also equal to vehicle plate number)')
    lot_id = fields.Many2one('stock.lot', string='Lot/Serial')

    # -- stubs: signatures preserved so views / Studio buttons stay valid ----
    def get_eid(self, token):
        raise UserError(_REMOVED)

    def get_response_from_fios_api(self, eid):
        raise UserError(_REMOVED)

    def get_sync_key_record(self, *args, **kwargs):
        return False

    def update_create_sync_key(self, *args, **kwargs):
        return False

    def get_fleet_vehicle(self, *args, **kwargs):
        return False

    def remove_matching_line_data(self, *args, **kwargs):
        return False

    def get_active_units(self, *args, **kwargs):
        raise UserError(_REMOVED)

    def create_fleet_contracts(self, *args, **kwargs):
        raise UserError(_REMOVED)
