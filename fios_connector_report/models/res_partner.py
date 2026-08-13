# -*- encoding: utf-8 -*-
from odoo import models, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def action_fios_active_units_send(self):
        return {
            'name': _('FIOS Active Unit Report'),
            'type': 'ir.actions.act_window',
            'res_model': 'fios.unit.report.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('fios_connector_report.fios_unit_report_wizard_view').id,
            'target': 'new'
        }
