# -*- encoding: utf-8 -*-

from odoo import api, fields, models, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    coordination_by_id = fields.Many2one('hr.employee', string='Coordination By')
    billing_by_id = fields.Many2one('hr.employee', string='Billing By')

    def write(self, vals):
        """
        Override core method to update coordination by id and billing by id to child partners
        :param vals:
        :return:
        """
        for rec in self:
            company_type = vals.get('company_type', False) or rec.company_type
            # get child partners
            child_partners = rec.env['res.partner'].search([('parent_id', '=', rec.id)])
            if (('coordination_by_id' or 'billing_by_id') in vals) and child_partners and company_type == 'company':
                coordination_by_id = vals.get('coordination_by_id', False) or rec.coordination_by_id.id
                billing_by_id = vals.get('billing_by_id', False) or rec.billing_by_id.id
                # update values to child_partners(we added context because we need to skip elif from first update)
                child_partners.with_context(child_partners=1).update({
                    'coordination_by_id': coordination_by_id,
                    'billing_by_id': billing_by_id,
                })
            # update values from parent company
            elif company_type != 'company' and not rec.env.context.get('child_partners', False):
                parent_id = vals.get('parent_id', False) or rec.parent_id.id
                parent_id = rec.env['res.partner'].browse(parent_id)
                if parent_id:
                    vals.update({
                        'coordination_by_id': parent_id.coordination_by_id.id,
                        'billing_by_id': parent_id.billing_by_id.id,
                    })
        res = super(ResPartner, self).write(vals)
        return res

    @api.model
    def create(self, vals):
        """
        Override core method to update coordination by id and billing by id from parent_id
        :param vals:
        :return:
        """
        res = super(ResPartner, self).create(vals)
        if self.company_type != 'company':
            if self.parent_id:
                self.update({
                    'coordination_by_id': self.parent_id.coordination_by_id.id,
                    'billing_by_id': self.parent_id.billing_by_id.id,
                })
        return res
