# -*- coding: utf-8 -*-
from odoo import fields, models, _, api


class FleetVehicleLogContract(models.Model):
    _inherit = 'fleet.vehicle.log.contract'

    partner_id = fields.Many2one('res.partner', string="Billing Contact Name")
    is_activated = fields.Boolean(string="Activated", tracking=True)
    activated_time = fields.Datetime(string='Activated Time')
    driver_company_id = fields.Many2one('res.partner', string="Driver Company", compute='_compute_company', store=False)
    sale_id = fields.Many2one('sale.order', string="Sale Order", compute='_get_related_so')

    user_id = fields.Many2one(default=lambda self: self._default_contract_user())

    def _default_contract_user(self):
        active_id = self.env.context.get('active_id')
        vehicle = self.env['fleet.vehicle']
        if isinstance(active_id, int) and self.env.context.get('active_model') == 'fleet.vehicle':
            vehicle = vehicle.browse(active_id).exists()
        return vehicle.manager_id or self.env.user

    @api.depends()
    def _get_related_so(self):
        for rec in self:
            rec.sale_id = rec.x_lot_id.sale_order_ids.sorted(key=lambda r: r.date_order)[-1].id if rec.x_lot_id.sale_order_ids else False

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

    @api.model_create_multi
    def create(self, vals_list):
        """Override core method to write activated time, if contract activated when creating"""
        for vals in vals_list:
            if vals.get('is_activated'):
                vals.update({'activated_time': fields.Datetime.now()})
        return super().create(vals_list)