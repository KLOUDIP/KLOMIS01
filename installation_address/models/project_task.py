from odoo import models, fields, api, _

class ProjectTas(models.Model):
    _inherit = 'project.task'

    @api.model
    def create(self, values):
        rec = super(ProjectTas, self).create(values)
        val = rec.partner_id.address_get(['installation'])
        rec.partner_id = val['installation']
        return rec
