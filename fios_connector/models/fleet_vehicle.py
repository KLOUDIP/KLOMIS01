# -*- encoding: utf-8 -*-

from odoo import api, fields, models, _


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    fios_plate_no_updated = fields.Boolean(string='FIOS Sync-Key Updated', help='This field will true when the user matched FIOS Sync-Key with the current vehicle plate number')

    @api.depends('name', 'brand_id')
    def name_get(self):
        """Overload Core Method"""
        res = []
        for record in self:
            if 'view_license_plate' in self.env.context:
                name = record.license_plate
            else:
                name = record.name
                if record.brand_id.name:
                    name = record.brand_id.name + '/' + name
            res.append((record.id, name))
        return res
