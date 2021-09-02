# -*- encoding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class FleetVehicleLogContract(models.Model):
    _inherit = 'fleet.vehicle.log.contract'

    fios_active_unit_available = fields.Boolean('FIOS Active Unit Available')
    color_index = fields.Integer(string='Color Index', compute='_compute_color_index')

    def _compute_color_index(self):
        """Get color index for the many2many widget"""
        for rec in self:
            color_index = 4
            if rec.state == 'expired':
                color_index = 1
            rec.write({'color_index': color_index})

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
            lot_id = self.env['stock.production.lot'].browse(self._context.get('default_x_lot_id'))
            stock_move_line = self.env['stock.move.line'].search([('lot_id', '=', lot_id.name)])
            if not stock_move_line:
                raise ValidationError(_('No traceability for the respective serial number(%s).') % lot_id.name)
            else:
                # we needed to update vehicle id or contract id state for the assigned vehicle in the last move line,
                # that belongs to the serial
                move_line = stock_move_line[-1]
                # check the type of the picking in move line, we needed to raise an error if the move line picking type
                # is incoming(return) otherwise update the vehicle or contract
                if move_line.picking_id.picking_type_id.code == 'incoming':
                    raise ValidationError(_('Type of the last traceability line for the serial(%s) is return. You '
                                            'cannot update vehicle to a return. \n\n Sale order - %s\n Return - %s') %
                                          (lot_id.name, move_line.picking_id.sale_id.name, move_line.picking_id.name))
                else:
                    # expire contract if contract assigned
                    if move_line.x_contract_id:
                        move_line.x_contract_id.write({'state': 'expired', 'expiration_date': fields.Datetime.today()})
                    _logger.info(_('Updating vehicle number to delivery \'%s\' belongs to sale order %s') % (move_line.picking_id.name, move_line.picking_id.sale_id.name))
                    # write values to move line
                    move_line.write({'x_vehicle_id': self._context.get('default_vehicle_id'), 'x_contract_id': res.id})
                    # update contract start date
                    res.update({'start_date': move_line.date.date()})

        # run get active units function for prevent multiple contacts creation
        if self.env.context.get('active_model') == 'active.units':
            self.env['active.units'].browse(self.env.context.get('active_id')).partner_id.get_active_units()
        return res
