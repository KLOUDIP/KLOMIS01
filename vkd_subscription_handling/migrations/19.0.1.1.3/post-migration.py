# -*- coding: utf-8 -*-
"""Remove optional-product blocks that were injected into live eCommerce carts.

Before 19.0.1.1.3 ``sale.order.write()`` appended an "Optional Products"
section to *any* draft subscription order, including the carts customers build
on /shop. Those lines are plain sale.order.line records, so they rendered in
the cart, in checkout and in the portal as if the customer had chosen them.

This drops the block from draft website orders only. Quotations a salesperson
prepared internally are left untouched - the block is intended there.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # Optional sections on draft website orders, plus everything parented to
    # them. Matching by parent_id is not enough on its own: rows written before
    # the sequence fix may have a stale parent, so the section's own id is the
    # anchor and the child lines are taken from parent_id.
    cr.execute("""
        SELECT sol.id
          FROM sale_order_line sol
          JOIN sale_order so ON so.id = sol.order_id
         WHERE sol.display_type = 'line_section'
           AND sol.is_optional IS TRUE
           AND so.state = 'draft'
           AND so.website_id IS NOT NULL
    """)
    section_ids = [row[0] for row in cr.fetchall()]
    if not section_ids:
        _logger.info("vkd_subscription_handling: no injected cart options found")
        return

    # Only delete child lines the customer never touched (qty 0). A line with a
    # quantity is one they deliberately added - keep it and let it become a
    # normal cart line by detaching it from the section.
    cr.execute("""
        DELETE FROM sale_order_line
         WHERE parent_id = ANY(%s)
           AND COALESCE(product_uom_qty, 0) = 0
    """, (section_ids,))
    removed_lines = cr.rowcount

    cr.execute("""
        UPDATE sale_order_line
           SET parent_id = NULL
         WHERE parent_id = ANY(%s)
    """, (section_ids,))
    kept_lines = cr.rowcount

    cr.execute("DELETE FROM sale_order_line WHERE id = ANY(%s)", (section_ids,))

    _logger.info(
        "vkd_subscription_handling: cleaned %s optional sections from draft "
        "website carts (%s option lines removed, %s kept as normal lines)",
        len(section_ids), removed_lines, kept_lines,
    )
