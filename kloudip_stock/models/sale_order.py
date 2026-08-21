# -*- coding: utf-8 -*-
import logging
from collections import defaultdict

from odoo import api, models

_logger = logging.getLogger(__name__)

# How far to walk the move chain in each direction. A 3-step delivery needs 2;
# anything beyond a handful is a data problem, not a deeper route.
_CHAIN_DEPTH = 6


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _get_related_transfers(self):
        """Every transfer that belongs to this order, resolved live.

        ``sale.order.picking_ids`` is a One2many on ``stock.picking.sale_id``,
        and ``sale_id`` is a *stored* computed field. When it is NULL - because
        the picking's own moves carry no ``sale_line_id``, which is the normal
        case for the internal steps of a multi-step delivery - the transfer
        silently drops off the Delivery stat button even though its Source
        Document still names the order.

        Recomputing ``sale_id`` fixes it going forward, but a stored field only
        recomputes when a dependency changes, so historical rows stay NULL until
        something touches them. This resolves the set at read time instead, so
        the stat button is correct whatever state ``sale_id`` is in:

          * ``picking_ids`` - whatever core already linked;
          * the move chain in both directions, which is how a PICK step reaches
            the OUT move that carries the sale line;
          * transfers whose Source Document names this order;
          * backorders and returns of anything found above.
        """
        self.ensure_one()
        Picking = self.env['stock.picking']
        pickings = self.picking_ids

        # 1. Walk the move chain both ways.
        seen = self.env['stock.move']
        frontier = self.order_line.move_ids
        for _depth in range(_CHAIN_DEPTH):
            frontier = frontier - seen
            if not frontier:
                break
            seen |= frontier
            frontier = frontier.move_orig_ids | frontier.move_dest_ids
        pickings |= seen.picking_id

        # 2. Source Document. Matched exactly against the comma-separated parts
        #    so that SO4139 cannot pick up SO41397's transfers.
        if self.name:
            candidates = Picking.search([
                ('origin', 'ilike', self.name),
                ('company_id', '=', self.company_id.id),
            ])
            pickings |= candidates.filtered(
                lambda p: self.name in [
                    part.strip() for part in (p.origin or '').split(',')
                ]
            )

        # 3. Backorders and returns of everything found so far, transitively.
        for _depth in range(_CHAIN_DEPTH):
            extra = Picking.search([
                '|',
                ('backorder_id', 'in', pickings.ids),
                ('return_id', 'in', pickings.ids),
            ])
            if not (extra - pickings):
                break
            pickings |= extra

        return pickings

    @api.depends('picking_ids')
    def _compute_picking_ids(self):
        """Count what the stat button will actually show.

        Kept deliberately cheap - one extra search for the whole recordset, no
        chain walking - because this runs for every order rendered in a list.
        The full resolution happens on click, in action_view_delivery.
        """
        super()._compute_picking_ids()

        names = [name for name in self.mapped('name') if name]
        if not names:
            return

        by_origin = defaultdict(lambda: self.env['stock.picking'])
        for picking in self.env['stock.picking'].search([('origin', 'in', names)]):
            by_origin[picking.origin] |= picking

        empty = self.env['stock.picking']
        for order in self:
            order.delivery_count = len(order.picking_ids | by_origin.get(order.name, empty))

    def action_view_delivery(self):
        return self._get_action_view_picking(self._get_related_transfers())
