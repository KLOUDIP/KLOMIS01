# -*- coding: utf-8 -*-
from odoo import fields, models, _, api

class FleetVehicleLogContract(models.Model):
    _inherit = 'fleet.vehicle.log.contract'

    partner_id = fields.Many2one('res.partner', string="Billing Contract")
    is_activated = fields.Boolean(string="Activated")

    @api.onchange('purchaser_id')
    def _onchange_purchaser(self):
        partners = []
        if self.purchaser_id:
            partners = self.purchaser_id.parent_id.child_ids.ids if self.purchaser_id.parent_id else self.purchaser_id.child_ids.ids
            
        return {'domain': {'partner_id': [('id', 'in', partners)]}}


