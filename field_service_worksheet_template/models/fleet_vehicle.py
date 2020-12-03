# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    @api.depends('name')
    def name_get(self):
        res = []
        for record in self:
            if self.env.context.get('params') is not None:
                if self.env.context.get('params').get('model') == 'project.task':
                    name = record.license_plate
                    res.append((record.id, name))
                else:
                    name = record.name
                    res.append((record.id, name))
            else:
                name = record.name
                res.append((record.id, name))
        return res
