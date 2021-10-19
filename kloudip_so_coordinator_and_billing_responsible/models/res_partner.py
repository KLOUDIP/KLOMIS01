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
        company_type = vals.get('company_type', False) or self.company_type
        # get child partners
        child_partners = self.env['res.partner'].search([('parent_id', '=', self.id)])
        if (('coordination_by_id' or 'billing_by_id') in vals) and child_partners and company_type == 'company':
            coordination_by_id = vals.get('coordination_by_id', False) or self.coordination_by_id.id
            billing_by_id = vals.get('billing_by_id', False) or self.billing_by_id.id
            # update values to child_partners(we added context because we need to skip elif from first update)
            child_partners.with_context(child_partners=1).update({
                'coordination_by_id': coordination_by_id,
                'billing_by_id': billing_by_id,
            })
        # update values from parent company
        elif company_type != 'company' and not self.env.context.get('child_partners', False):
            parent_id = vals.get('parent_id', False) or self.parent_id.id
            parent_id = self.env['res.partner'].browse(parent_id)
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
            self.update({
                'coordination_by_id': self.parent_id.coordination_by_id.id,
                'billing_by_id': self.parent_id.billing_by_id.id,
            })
        return res
