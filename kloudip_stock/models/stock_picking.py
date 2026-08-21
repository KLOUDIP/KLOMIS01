# -*- coding: utf-8 -*-
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    @api.depends(
        'reference_ids.sale_ids',
        'move_ids.sale_line_id.order_id',
        'move_ids.move_dest_ids.sale_line_id.order_id',
        'move_ids.move_orig_ids.sale_line_id.order_id',
        'origin',
    )
    def _compute_sale_id(self):
        """Keep backorders on the Sales Order's Transfers list.

        ``sale.order.picking_ids`` is a One2many on ``stock.picking.sale_id``, so
        a picking only appears under the Delivery stat button when its ``sale_id``
        is set. Core computes it like this (sale_stock/models/stock.py)::

            @api.depends('reference_ids.sale_ids', 'move_ids.sale_line_id.order_id')
            def _compute_sale_id(self):
                for picking in self:
                    sales_order = picking.move_ids.sale_line_id.order_id
                    picking.sale_id = sales_order[0] if sales_order else False

        ``reference_ids.sale_ids`` is declared as a dependency but the body never
        reads it, so the only accepted link is ``move_ids.sale_line_id``.

        A backorder is created by ``_create_backorder_picking()`` as
        ``self.copy({'move_ids': [], ...})`` and the moves are written onto it
        immediately afterwards. That write re-triggers this compute, and any
        backordered move that does not itself carry a ``sale_line_id`` - the
        normal case for the internal steps of a 2/3-step delivery, where only the
        outgoing move is linked to the order line - leaves ``sale_id`` empty. The
        backorder then disappears from the Sales Order while still showing the
        order in its own Source Document.

        Fill the gap the way the dependency list already promises: fall back to
        the stock references carried by the moves, which do point at the sale
        order, then to the move chain, then to the picking this one was split
        from or returned from, and finally to the Source Document.

        Purely additive - a link core already found is never removed.
        """
        super()._compute_sale_id()
        for picking in self:
            if picking.sale_id:
                continue

            # 1. The stock.reference chain, which sale_stock links to the order
            #    and which backordered moves carry over.
            sales_order = picking.reference_ids.sale_ids
            if sales_order:
                picking.sale_id = sales_order[0]
                continue

            # 2. The move chain. An internal step of a multi-step delivery
            #    carries no sale_line_id of its own, but the outgoing move it
            #    feeds does - follow move_dest_ids, and the other way round for
            #    a return.
            chain = (
                picking.move_ids.move_dest_ids.sale_line_id.order_id
                or picking.move_ids.move_orig_ids.sale_line_id.order_id
            )
            if chain:
                picking.sale_id = chain[0]
                continue

            # 3. A backorder belongs to the same order as the picking it was
            #    split from, and a return to the same order as its origin.
            #    Deliberately not in @api.depends - backorder_id.sale_id there
            #    would make this a recursive field, and it is not needed:
            #    backorder_id is already set when the moves are attached, which
            #    is what triggers this compute.
            parent = picking.backorder_id.sale_id or picking.return_id.sale_id
            if parent:
                picking.sale_id = parent
                continue

            # 4. Last resort: the Source Document. If the transfer says
            #    "SO41397" it belongs under SO41397 - that is exactly what the
            #    user reads on screen. Only an unambiguous, same-company, exact
            #    name match is accepted.
            picking.sale_id = picking._sale_order_from_origin()

    def _sale_order_from_origin(self):
        """Resolve `origin` ("Source Document") to a single sale.order, or False."""
        self.ensure_one()
        if not self.origin:
            return False
        names = [part.strip() for part in self.origin.split(',') if part.strip()]
        if not names:
            return False
        orders = self.env['sale.order'].search(
            [('name', 'in', names), ('company_id', '=', self.company_id.id)],
            limit=2,
        )
        return orders if len(orders) == 1 else False

    @api.model
    def action_relink_transfers_to_sale_orders(self, pickings=None):
        """Re-run _compute_sale_id on transfers that lost their Sales Order.

        The compute above only fires when one of its dependencies changes, so
        transfers that were already orphaned keep their stored ``sale_id = NULL``
        after the module is upgraded. This queues them for recomputation.

        Running it inside the compute means the ``_set_sale_id`` inverse is not
        called, so no stock.reference is created and no sale line is reassigned -
        only the missing link is filled in.

        Idempotent: transfers that genuinely belong to no order stay unlinked, so
        re-running finds the same (shrinking) set and changes nothing else.
        """
        if not pickings:
            pickings = self.search([('sale_id', '=', False)])
        _logger.info("Relink transfers: recomputing sale_id on %s transfer(s)", len(pickings))

        self.env.add_to_compute(self._fields['sale_id'], pickings)
        self.env.flush_all()

        linked = pickings.filtered('sale_id')
        for picking in linked:
            _logger.info("  %s -> %s", picking.name, picking.sale_id.name)
        _logger.info(
            "Relink transfers: %s of %s transfer(s) now point at a sales order",
            len(linked), len(pickings),
        )
        return {'checked': len(pickings), 'linked': len(linked)}

    def action_diagnose_sale_link(self):
        """Explain, per transfer, why it is or is not attached to a Sales Order.

        Select the transfer in Inventory > Transfers and run
        "Diagnose Sales Order Link" from the Actions menu; the report goes to the
        server log (Odoo.sh: the branch's Logs tab).
        """
        for picking in self:
            _logger.info("=" * 70)
            _logger.info("%s  (id=%s, type=%s, state=%s)",
                         picking.name, picking.id,
                         picking.picking_type_id.code, picking.state)
            _logger.info("  sale_id            : %s", picking.sale_id.name or "EMPTY")
            _logger.info("  origin             : %s", picking.origin or "-")
            _logger.info("  backorder_id       : %s -> sale_id %s",
                         picking.backorder_id.name or "-",
                         picking.backorder_id.sale_id.name or "-")
            _logger.info("  return_id          : %s -> sale_id %s",
                         picking.return_id.name or "-",
                         picking.return_id.sale_id.name or "-")
            _logger.info("  reference_ids      : %s",
                         ", ".join(picking.reference_ids.mapped('name')) or "-")
            _logger.info("  reference sale_ids : %s",
                         ", ".join(picking.reference_ids.sale_ids.mapped('name')) or "-")
            _logger.info("  moves              : %s", len(picking.move_ids))
            for move in picking.move_ids:
                _logger.info(
                    "    move %-7s %-40s sale_line=%s dest=%s orig=%s refs=%s",
                    move.id,
                    move.product_id.display_name[:40],
                    move.sale_line_id.order_id.name or "-",
                    ", ".join(move.move_dest_ids.sale_line_id.order_id.mapped('name')) or "-",
                    ", ".join(move.move_orig_ids.sale_line_id.order_id.mapped('name')) or "-",
                    ", ".join(move.reference_ids.mapped('name')) or "-",
                )
            _logger.info("  origin resolves to : %s",
                         picking._sale_order_from_origin().name or "-")
        _logger.info("=" * 70)
        return True
