# -*- coding: utf-8 -*-
from odoo import fields, models, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    contract_ids = fields.One2many('fleet.vehicle.log.contract', 'partner_id', string="Contract")
    contract_count = fields.Integer(string="Contracts", compute='_compute_contract_count', store=False)
    active_contract_counts = fields.Integer(string="Active Fleet", compute='_compute_active_contract_count', store=False)

    @api.depends('contract_ids')
    def _compute_contract_count(self):
        for contract in self:
            if contract.child_ids:
                fleet_count = self.env['fleet.vehicle.log.contract'].search_count([('partner_id', 'in', contract.child_ids.ids), ('state', '!=', 'closed')])
                contract.contract_count = fleet_count
            else:
                fleet_count = self.env['fleet.vehicle.log.contract'].search_count([('partner_id', '=', contract.id), ('state', '!=', 'closed')])
                contract.contract_count = fleet_count

    @api.depends('contract_ids')
    def _compute_active_contract_count(self):
        for contract in self:
            if contract.child_ids:
                fleet_count = self.env['fleet.vehicle.log.contract'].search_count([('partner_id', 'in', contract.child_ids.ids), ('is_activated', '=', True), ('state', '!=', 'closed')])
                contract.active_contract_counts = fleet_count
            else:
                fleet_count = self.env['fleet.vehicle.log.contract'].search_count([('partner_id', '=', contract.id), ('is_activated', '=', True), ('state', '!=', 'closed')])
                contract.active_contract_counts = fleet_count

    def action_view_partner_contracts(self):
        contract_form_view = self.env.ref('fleet.fleet_vehicle_log_contract_view_form')
        contract_list_view = self.env.ref('fleet.fleet_vehicle_log_contract_view_tree')
        if self.child_ids:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Contract logs',
                'res_model': 'fleet.vehicle.log.contract',
                'domain': [('partner_id', 'in', self.child_ids.ids), ('state', '!=', 'closed')],
                'views': [(contract_list_view.id, 'tree'), (contract_form_view.id, 'form')],
            }
        else:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Contract logs',
                'res_model': 'fleet.vehicle.log.contract',
                'domain': [('partner_id', '=', self.id), ('state', '!=', 'closed')],
                'views': [(contract_list_view.id, 'tree'), (contract_form_view.id, 'form')],
            }

    def action_view_partner_active_contracts(self):
        contract_form_view = self.env.ref('fleet.fleet_vehicle_log_contract_view_form')
        contract_list_view = self.env.ref('fleet.fleet_vehicle_log_contract_view_tree')
        if self.child_ids:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Contract logs',
                'res_model': 'fleet.vehicle.log.contract',
                'domain': [('partner_id', '=', self.child_ids.ids), ('is_activated', '=', True)],
                'views': [(contract_list_view.id, 'tree'), (contract_form_view.id, 'form')],
            }
        else:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Contract logs',
                'res_model': 'fleet.vehicle.log.contract',
                'domain': [('partner_id', '=', self.id), ('is_activated', '=', True)],
                'views': [(contract_list_view.id, 'tree'), (contract_form_view.id, 'form')],
            }

