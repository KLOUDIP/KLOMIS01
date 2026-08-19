# -*- coding: utf-8 -*-
# KLOMIS01 v17 -> v19 REMOVAL SHELL - load-only.
from odoo import fields, models


class FleetVehicleLogContract(models.Model):
    _inherit = 'fleet.vehicle.log.contract'

    fios_active_unit_available = fields.Boolean('FIOS Active Unit Available')
    color_index = fields.Integer(string='Color Index', compute='_compute_color_index')

    def _compute_color_index(self):
        # v17 used rec.write() inside a non-stored compute, which is both a
        # recursion hazard and illegal on a readonly field. Plain assignment.
        for rec in self:
            rec.color_index = 1 if rec.state == 'expired' else 4
