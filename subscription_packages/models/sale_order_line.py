from odoo import api, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.depends(
        "product_id",
        "linked_line_id",
        "linked_line_ids",
        "order_id.rental_start_date",
        "order_id.rental_return_date",
        "is_rental",
    )
    def _compute_name(self):

        recurring_lines = self.env["sale.order.line"]
        normal_lines = self.env["sale.order.line"]

        for line in self:
            if not line.order_id:
                continue

            if (
                line.recurring_invoice
                and line.product_id
                and line.product_id in line.order_id.sale_order_recurring_ids.product_id
            ):
                recurring_lines |= line
            else:
                normal_lines |= line

        if normal_lines:
            super(SaleOrderLine, normal_lines)._compute_name()

