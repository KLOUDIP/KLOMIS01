# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    @api.depends('name', 'license_plate')
    def _compute_display_name(self):
        for record in self:
            if self.env.context.get('get_license') and self.env.context.get('default_x_project_task_id') is None:
                record.display_name = record.license_plate
            else:
                record.display_name = record.name
