# -*- encoding: utf-8 -*-
import logging
import calendar
from datetime import datetime

from odoo import models, Command

_logger = logging.getLogger(__name__)


class ActiveUnits(models.Model):
    _inherit = 'active.units'

    def write(self, vals):
        rec = super(ActiveUnits, self).write(vals)
        if 'contract_ids' in vals:
            contract_id = vals.get('contract_ids')[0]
            if contract_id:
                self.update_coordinator_unit_line(contract_id[1])
        return rec

    def update_coordinator_unit_line(self, contract_id):
        sale_order = self.env['fleet.vehicle.log.contract'].browse(contract_id).sale_id
        if sale_order:
            last_day = calendar.monthrange(sale_order.date_order.year, sale_order.date_order.month)[1]
            first_day = sale_order.date_order.replace(day=1).date()
            last_date = datetime(year=sale_order.date_order.year, month=sale_order.date_order.month, day=last_day).date()

            order_ids = self.env['sale.order'].search([('date_order', '>=', first_day), ('date_order', '<=', last_date), ('coordinator_id', '=', sale_order.coordinator_id.id)])
            contracts_count = self.env['fleet.vehicle.log.contract'].search_count([('sale_id', 'in', order_ids)])

            month = sale_order.date_order.month
            year = sale_order.date_order.year
            if sale_order.coordinator_id.employee_id:
                unit_line = self.env['coordinator.unit.line'].search([('employee_id', '=', sale_order.coordinator_id.employee_id.id), ('year', '=', year), ('month', '=', str(month))])
                if unit_line:
                    unit_line.count = contracts_count
                else:
                    sale_order.coordinator_id.employee_id.write({
                        'coordinator_assigned_ids': [Command.create({
                            'year': str(year),
                            'month': str(month),
                            'count': contracts_count,
                            'employee_id': sale_order.coordinator_id.employee_id.id
                        })]
                    })