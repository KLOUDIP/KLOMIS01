# -*- coding: utf-8 -*-
from odoo import fields, models, _

class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    worksheet_count = fields.Integer(string="Worksheet Count", compute="_get_worksheet_count")

    def _get_worksheet_count(self):
        worksheets = self.env['worksheet.template.line'].search_count([('fleet_id', '=', self.id)])
        self.worksheet_count = worksheets

    def open_worksheets(self):
        return {
            'domain': [('fleet_id', '=', self.id)],
            'name': 'Fleet Vehicle Worksheet',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'worksheet.template.line',
            'view_id': False,
            'views': [(self.env.ref('field_service_worksheet_template.cites_tree_view').id, 'tree'),
                      (self.env.ref('field_service_worksheet_template.worksheet_template_line_form').id, 'form')],
            'type': 'ir.actions.act_window'
        }
