# -*- encoding: utf-8 -*-
from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    coordination_by_id = fields.Many2one('hr.employee', string='Coordination By')
    billing_by_id = fields.Many2one('hr.employee', string='Billing By')

    def write(self, vals):
        """ Override core method to update coordination and billing to child partners """
        res = super(ResPartner, self).write(vals)

        # Only trigger child updates if the specific fields were changed
        if 'coordination_by_id' in vals or 'billing_by_id' in vals:
            for rec in self:
                if rec.company_type == 'company':
                    child_partners = self.env['res.partner'].search([('parent_id', '=', rec.id)])
                    if child_partners:
                        update_dict = {}
                        if 'coordination_by_id' in vals:
                            update_dict['coordination_by_id'] = vals['coordination_by_id']
                        if 'billing_by_id' in vals:
                            update_dict['billing_by_id'] = vals['billing_by_id']

                        # Apply to children without recursion
                        child_partners.write(update_dict)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        """ Override core method to inherit coordination and billing from parent_id """
        for vals in vals_list:
            if vals.get('parent_id') and vals.get('company_type') != 'company':
                parent_id = self.env['res.partner'].browse(vals['parent_id'])
                if parent_id:
                    if 'coordination_by_id' not in vals:
                        vals['coordination_by_id'] = parent_id.coordination_by_id.id
                    if 'billing_by_id' not in vals:
                        vals['billing_by_id'] = parent_id.billing_by_id.id

        return super(ResPartner, self).create(vals_list)
