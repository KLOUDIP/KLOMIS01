# -*- coding: utf-8 -*-
from odoo import fields, models, _, api


class FleetVehicleLogContract(models.Model):
    _inherit = 'fleet.vehicle.log.contract'

    partner_id = fields.Many2one('res.partner', string="Billing Contact")
    is_activated = fields.Boolean(string="Activated")
    activated_time = fields.Datetime(string='Activated Time')
    driver_company_id = fields.Many2one('res.partner', string="Driver Company", compute='_compute_company', store=False)

    @api.depends('purchaser_id')
    def _compute_company(self):
        for i in self:
            i['driver_company_id'] = self.purchaser_id.parent_id
            
    def write(self, vals):
        """Override core method to write activated/ deactivated time"""
        if 'is_activated' in vals:
            vals.update({'activated_time': fields.Datetime.now()})
        return super(FleetVehicleLogContract, self).write(vals)