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
        _logger.info("--------------------active.units - create--------------------")
        _logger.info(values)
        records = super(ActiveUnits, self).create(values)
        for rec in records:
            contracts = rec.contract_ids.filtered(lambda x: x.sale_id.coordinator_id.id == False)
            if len(contracts) > 0:
                rec.write({'contract_ids': [(3, contract.id) for contract in contracts]})
            else:
                contracts = rec.contract_ids.filtered(lambda x: x.sale_id.coordinator_id.id != False)
                if len(contracts) > 0:
                    self.update_monthly_rec(contracts[0].id)
                    self.update_coordinator_unit_line(contracts[0].id, 'add')
        return records

    def write(self, vals):
        _logger.info("--------------------active.units - write--------------------")
        _logger.info(vals)
        rec = super(ActiveUnits, self).write(vals)
        if 'contract_ids' in vals:
            for contract in vals.get('contract_ids', []):
                if contract[0] == 4:
                    self.update_monthly_rec(contract[1])
                    self.update_coordinator_unit_line(contract[1], 'add')
                elif contract[0] == 6:
                    if len(contract[2]) > 0:
                        self.update_monthly_rec(contract[2][0])
                        self.update_coordinator_unit_line(contract[2][0], 'add')
                else:
                    self.unlink_monthly_rec(contract[1])
                    self.update_coordinator_unit_line(contract[1], 'remove')
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
        _logger.info(rec.contract_id.name)
        if rec:
            rec.unlink()

    def update_coordinator_unit_line(self, contract_id, action):
        contract = self.env['fleet.vehicle.log.contract'].browse(contract_id)
        sale_order = contract.sale_id
        today = datetime.now()
        if sale_order:
            if not sale_order.coordinator_id and action == 'add':
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
                    if action == 'remove' and unit_count <= 0:
                        unit_count = unit_line.count - 1
                    unit_line.write({'count': unit_count})
                else:
                    if action == 'remove' and unit_count <= 0:
                        unit_count -= 1
                    sale_order.coordinator_id.employee_id.write({
                        'coordinator_assigned_ids': [Command.create({
                            'year': str(year),
                            'month': str(month),
                            'count': unit_count,
                            'employee_id': sale_order.coordinator_id.employee_id.id
                        })]
                    })
                if action == 'add':
                    message = f'Contract Added {contract.name}'
                else:
                    message = f'Contract Removed {contract.name}'
                self.partner_id.message_post(
                    body=message
                )


class ActiveUnitsMonthly(models.Model):
    _name = "active.units.monthly"

    date = fields.Date(string="Date")
    contract_id = fields.Many2one("fleet.vehicle.log.contract", string="Contract")
    unit_id = fields.Many2one("active.units", string="Active Unit")
