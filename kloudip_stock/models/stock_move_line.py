from collections import Counter, defaultdict

from odoo import _, api, fields, tools, models


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    @api.onchange('location_id')
    def set_serial_number_filtration(self):
        """Filter LOT IDs when select the From location in stock move line"""
        lot_ids = []
        if self.picking_id.picking_type_code in ['outgoing', 'internal']:
            if self.product_id and self.location_id:
                if self.product_id.tracking == 'serial':
                    quants = self.env['stock.quant'].search([('product_id', '=', self.product_id.id),
                                                             ('location_id', '=', self.location_id.id),
                                                             ('quantity', '!=', 0),
                                                             '|', ('location_id.usage', '=', 'customer'),
                                                             '&', ('company_id', '=', self.company_id.id),
                                                             ('location_id.usage', 'in', ('internal', 'transit'))])
                    serial_numbers = quants.mapped('lot_id')
                    if serial_numbers:
                        lot_ids = serial_numbers.ids

                    return {'domain': {'lot_id': [('id', 'in', lot_ids)]}}

    @api.onchange('lot_name', 'lot_id')
    def _onchange_serial_number(self):
        """ When the user is encoding a move line for a tracked product, we apply some logic to
        help him. This includes:
            - automatically switch `qty_done` to 1.0
            - warn if he has already encoded `lot_name` in another move line
            - warn (and update if appropriate) if the SN is in a different source location than selected
        """
        res = {}
        if self.product_id.tracking == 'serial':
            if not self.qty_done:
                self.qty_done = 1

            message = None
            if self.lot_name or self.lot_id:
                move_lines_to_check = self._get_similar_move_lines() - self
                if self.lot_name:
                    counter = Counter([line.lot_name for line in move_lines_to_check])
                    if counter.get(self.lot_name) and counter[self.lot_name] > 1:
                        message = _(
                            'You cannot use the same serial number twice. Please correct the serial numbers encoded.')
                    elif not self.lot_id:
                        lots = self.env['stock.lot'].search([('product_id', '=', self.product_id.id),
                                                                        ('name', '=', self.lot_name),
                                                                        ('company_id', '=', self.company_id.id)])
                        quants = lots.quant_ids.filtered(
                            lambda q: q.quantity != 0 and q.location_id.usage in ['customer', 'internal', 'transit'])
                        if quants:
                            message = _(
                                'Serial number (%s) already exists in location(s): %s. Please correct the serial number encoded.',
                                self.lot_name, ', '.join(quants.location_id.mapped('display_name')))
                elif self.lot_id:
                    counter = Counter([line.lot_id.id for line in move_lines_to_check])
                    if counter.get(self.lot_id.id) and counter[self.lot_id.id] > 1:
                        message = _(
                            'You cannot use the same serial number twice. Please correct the serial numbers encoded.')
            if message:
                res['warning'] = {'title': _('Warning'), 'message': message}
        return res
