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
            if i.purchaser_id:
                child_ids = i.purchaser_id.parent_id.child_ids
                for rec in child_ids:
                    count = rec.subscription_count
                    if count > 0 and rec.type == 'invoice':
                        rec.subscription_count_boolean_field = True
                    else:
                        rec.subscription_count_boolean_field = False

    def write(self, vals):
        """Override core method to write activated/ deactivated time"""
        if 'is_activated' in vals:
            vals.update({'activated_time': fields.Datetime.now()})
        return super(FleetVehicleLogContract, self).write(vals)

    def create(self, vals):
        """Override core method to write activated time, if contract activated when creating"""
        if vals.get('is_activated'):
            vals.update({'activated_time': fields.Datetime.now()})
        return super(FleetVehicleLogContract, self).create(vals)
