# -*- encoding: utf-8 -*-
import logging
import calendar
from datetime import datetime

from odoo import models, Command, fields, api
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ActiveUnits(models.Model):
    _inherit = 'active.units'

    @api.model_create_multi
    def create(self, values):
        records = super(ActiveUnits, self).create(values)
        for rec in records:
            contracts = rec.contract_ids.filtered(lambda x: x.sale_id.coordinator_id.id == False)
            if contracts:
                rec.write({'contract_ids': [(4, contract.id) for contract in contracts]})
            else:
                contracts = rec.contract_ids.filtered(lambda x: x.sale_id.coordinator_id.id != False)
                self.update_monthly_rec(contracts[0].id)
        return records

    def write(self, vals):
        rec = super(ActiveUnits, self).write(vals)
        if 'contract_ids' in vals:
            if vals.get('contract_ids'):
                contract_id = vals.get('contract_ids')[0]
                if contract_id[0] == 4:
                    self.update_monthly_rec(contract_id[1])
                else:
                    self.unlink_monthly_rec(contract_id[1])
                self.update_coordinator_unit_line(contract_id[1])
        return rec

    def update_monthly_rec(self, contract_id):
        res = self.env['active.units.monthly'].create({
            'date': fields.Datetime.now(),
            'contract_id': contract_id,
            'unit_id': self.id
        })
        return res

    def unlink_monthly_rec(self, contract_id):
        rec = self.env['active.units.monthly'].search([('unit_id', '=', self.id), ('contract_id', '=', contract_id)])
        if rec:
            rec.unlink()

    def update_coordinator_unit_line(self, contract_id):
        sale_order = self.env['fleet.vehicle.log.contract'].browse(contract_id).sale_id
        today = datetime.now()
        if sale_order:
            if not sale_order.coordinator_id:
                raise ValidationError(f'Please, select a coordinator for this sale order - {sale_order.name}')
            last_day = calendar.monthrange(today.year, today.month)[1]
            first_day = today.replace(day=1).date()
            last_date = datetime(year=today.year, month=today.month, day=last_day).date()

            unit_count = self.env['active.units.monthly'].search_count([('date', '>=', first_day), ('date', '<=', last_date), ('contract_id', '=', contract_id)])

            month = today.month
            year = today.year
            if sale_order.coordinator_id.employee_id:
                unit_line = self.env['coordinator.unit.line'].search([('employee_id', '=', sale_order.coordinator_id.employee_id.id), ('year', '=', year), ('month', '=', str(month))])
                if unit_line:
                    unit_line.write({'count': unit_count})
                else:
                    sale_order.coordinator_id.employee_id.write({
                        'coordinator_assigned_ids': [Command.create({
                            'year': str(year),
                            'month': str(month),
                            'count': unit_count,
                            'employee_id': sale_order.coordinator_id.employee_id.id
                        })]
                    })


class ActiveUnitsMonthly(models.Model):
    _name = "active.units.monthly"

    date = fields.Date(string="Date")
    contract_id = fields.Many2one("fleet.vehicle.log.contract", string="Contract")
    unit_id = fields.Many2one("active.units", string="Active Unit")
