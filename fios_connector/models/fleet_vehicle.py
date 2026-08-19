# -*- coding: utf-8 -*-
# KLOMIS01 v17 -> v19 REMOVAL SHELL - load-only.
from odoo import fields, models


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    fios_plate_no_updated = fields.Boolean(
        string='FIOS Sync-Key Updated',
        help='This field will true when the user matched FIOS Sync-Key with the current vehicle plate number')

    # NOTE: the v17 name_get() override is dropped - name_get was removed from
    # the ORM in Odoo 17 and the method is dead code in 19.
