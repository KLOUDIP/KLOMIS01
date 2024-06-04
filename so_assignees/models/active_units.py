# -*- encoding: utf-8 -*-
import logging
import calendar
from datetime import datetime

from odoo import models, Command, fields, api
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ActiveUnits(models.Model):
    _inherit = 'active.units'

    coordinator_id = fields.Many2one("res.users", string="Assigned To", tracking=True)
    is_coordinator_add = fields.Boolean(string="Coordinator Added")

    @api.onchange('coordinator_id')
    def onchange_coordinator_id(self):
        if self.coordinator_id:
            if not self.contract_ids:
                raise ValidationError("Please, add a contract first.")
            if not self.contract_ids.mapped('sale_id').coordinator_id:
                raise ValidationError("Please, select the coordinator for the contract's SO")
            if self.contract_ids.mapped('sale_id').filtered(lambda x: x.coordinator_id.id != self.coordinator_id.id):
                raise ValidationError("Please, select the correct coordinator")
            if not all(self.contract_ids.mapped('activated_time')):
                raise ValidationError("This contract's activated date time is empty")
            self.update_monthly_rec(self.contract_ids[0]._origin, 1)
            self.update_coordinator_unit_line(self.contract_ids[0]._origin)
            self.is_coordinator_add = True
        else:
            if self.is_coordinator_add:
                self.update_monthly_rec(self.contract_ids[0]._origin, -1)
                self.update_coordinator_unit_line(self.contract_ids[0]._origin)
                _logger.info(self.contract_ids[0])
                _logger.info(self.contract_ids[0]._origin)
                self.is_coordinator_add = False

    def update_monthly_rec(self, contract_id, value):
        res = self.env['active.units.monthly'].create({
            'date': contract_id.activated_time.date() if contract_id.activated_time else fields.Datetime.now(),
            'contract_id': contract_id.id,
            'coordinator_id': contract_id.sale_id.coordinator_id.id,
            'unit_id': self.id,
            'value': value
        })
        if res.unit_id.partner_id:
            if res.value == 1:
                message = f"Unit removed by{res.coordinator_id.name}"
            else:
                message = f"Unit removed by{res.coordinator_id.name}"
            # res.unit_id.partner_id.message_notify(body=message)
        return res

    def update_coordinator_unit_line(self, contract_id):
        _logger.info(contract_id)
        contract = contract_id.activated_time if contract_id.activated_time else datetime.now()
        last_day = calendar.monthrange(contract.year, contract.month)[1]
        first_day = contract.replace(day=1).date()
        last_date = datetime(year=contract.year, month=contract.month, day=last_day).date()

        coordinator_id = contract_id.sale_id.coordinator_id.id
        if coordinator_id:
            unit_count = sum(self.env['active.units.monthly'].search([('date', '>=', first_day), ('date', '<=', last_date), ('coordinator_id', '=', coordinator_id)]).mapped('value'))
            _logger.info("unit_count")
            _logger.info(unit_count)
            month = contract.month
            year = contract.year
            if contract_id.sale_id:
                unit_line = self.env['coordinator.unit.line'].search([('employee_id', '=', contract_id.sale_id.coordinator_id.employee_id.id), ('year', '=', year), ('month', '=', str(month))])
                _logger.info("unit_line")
                _logger.info(unit_line.employee_id.name)
                if unit_line:
                    unit_line.write({'count': unit_count})
                else:
                    contract_id.sale_id.coordinator_id.employee_id.sudo().write({
                        'coordinator_assigned_ids': [Command.create({
                            'year': str(year),
                            'month': str(month),
                            'count': unit_count,
                            'employee_id': contract_id.sale_id.coordinator_id.employee_id.id
                        })]
                    })
                    
    def unlink(self):
        if self.coordinator_id:
            self.update_monthly_rec(self.contract_ids[0], -1)
            self.update_coordinator_unit_line(self.contract_ids[0])
        return super(ActiveUnits, self).unlink()


class ActiveUnitsMonthly(models.Model):
    _name = "active.units.monthly"

    date = fields.Date(string="Date")
    contract_id = fields.Many2one("fleet.vehicle.log.contract", string="Contract")
    coordinator_id = fields.Many2one("res.users", string="Assigned To")
    unit_id = fields.Many2one("active.units", string="Active Unit")
    value = fields.Integer(string="Value")
