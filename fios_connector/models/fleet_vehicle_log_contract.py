# -*- encoding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class FleetVehicleLogContract(models.Model):
    _inherit = 'fleet.vehicle.log.contract'

    fios_active_unit_available = fields.Boolean('FIOS Active Unit Available')

    @api.onchange('partner_id')
    def _onchange_billing_contract(self):
        """Check partner have subscriptions available"""
        subscription_count = len(self.env['sale.subscription'].search([('partner_id', '=', self.partner_id.id)]))
        if self.partner_id and subscription_count == 0:
            raise ValidationError(_('No subscriptions are available for the selected billing contact! \nYou need to select a billing contact which contains subscriptions.'))

    @api.model
    def create(self, vals):
        """Add vehicle to stock move line when creating contract from active units"""
        res = super(FleetVehicleLogContract, self).create(vals)
        if 'add_vehicle_to_stock_move_line' in self._context:
            # get sale order
            lot_id = self.env['stock.production.lot'].browse(self._context.get('default_x_lot_id'))
            if len(lot_id.sale_order_ids) > 1:
                _logger.info(_('Multiple sale orders found for serial \'%s\'. Getting last sale order') % lot_id.name)
                sale_id = lot_id.sale_order_ids[-1]
            elif len(lot_id.sale_order_ids) == 1:
                sale_id = lot_id.sale_order_ids
            else:
                raise ValidationError(_('No sale orders found for serial \'%s\'.') % lot_id.name)
            # update move line
            move_line = sale_id.picking_ids.filtered(lambda x: x.state in ['done']).mapped('move_line_ids_without_package').filtered(lambda x: x.lot_id.id == lot_id.id)
            if len(move_line) > 1:
                raise ValidationError(_('Multiple move lines found for serial %s. (sale order %s)') % (lot_id.name, sale_id.name))
            elif len(move_line) == 1:
                if move_line.x_vehicle_id:
                    raise ValidationError(_('Vehicle already assigned to move line. (Sale order: %s)') % sale_id.name)
                _logger.info(_('Updating vehicle number to delivery \'%s\' belong to sale order %s') % (move_line.picking_id.name, sale_id.name))
                move_line.write({'x_vehicle_id': self._context.get('default_vehicle_id'), 'x_contract_id': res.id})
            else:
                raise ValidationError(_('No move line found for serial %s. (sale order %s)') % (lot_id.name, sale_id.name))
        return res
