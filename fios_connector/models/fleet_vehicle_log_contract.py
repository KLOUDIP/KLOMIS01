# -*- encoding: utf-8 -*-

from odoo import api, fields, models, _


class FleetVehicleLogContract(models.Model):
    _inherit = 'fleet.vehicle.log.contract'

    fios_active_unit_available = fields.Boolean('FIOS Active Unit Available')