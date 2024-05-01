# -*- coding: utf-8 -*-
from odoo import fields, models, Command


class SaleOrder(models.Model):
    _inherit = "sale.order"

    coordinator_id = fields.Many2one("res.partner", string="Assigned To", tracking=True)

    def write(self, vals):
        rec = super(SaleOrder, self).write(vals)
        if 'coordinator_id' in vals:
            self.update_coordinator_unit_line()
        return rec

    def update_coordinator_unit_line(self):
        month = self.date_order.month
        year = self.date_order.year
        unit_line = self.env['coordinator.unit.line'].search([('partner_id', '=', self.partner_id.id), ('year', '=', year), ('month', '=', str(month))])
        unit_count = self.search_count([('coordinator_id', '=', self.coordinator_id.id)])
        if unit_line:
            unit_line.count = self.search_count([('coordinator_id', '=', self.coordinator_id.id)])
        else:
            self.coordinator_id.write({
                'coordinator_assigned_ids': [Command.create({
                    'year': str(year),
                    'month': str(month),
                    'count': unit_count,
                    'partner_id': self.coordinator_id.id
                })]
            })
