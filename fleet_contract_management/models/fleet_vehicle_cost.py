# -*- coding: utf-8 -*-
from odoo import fields, models, _

class FleetVehicleLogContract(models.Model):
    _inherit = 'fleet.vehicle.log.contract'

    partner_id = fields.Many2one('res.partner', string="Billing Contract")
    is_activated = fields.Boolean(string="Activated")
