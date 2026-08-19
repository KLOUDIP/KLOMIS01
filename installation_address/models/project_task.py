from odoo import models, api


class ProjectTask(models.Model):
    _inherit = 'project.task'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('partner_id'):
                partner = self.env['res.partner'].browse(vals['partner_id'])
                addr = partner.address_get(['installation'])
                # Swap to installation address before the record is created in the database
                if addr.get('installation'):
                    vals['partner_id'] = addr['installation']

        return super(ProjectTask, self).create(vals_list)
