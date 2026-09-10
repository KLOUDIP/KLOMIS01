import logging

from odoo import models

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _prepare_product_base_line_for_taxes_computation(self, product_line):
        """ Divide the combo child quantity by the combo item quantity.

        Delegates to super() so every key core puts in the base line dict
        ('name', 'special_type', the currency rate helper, ...) is preserved.
        Rebuilding the dict here silently drops those keys and breaks callers
        such as the Factur-X/UBL export (KeyError: 'name').
        """
        self.ensure_one()
        base_line = super()._prepare_product_base_line_for_taxes_computation(product_line)

        combo_item = product_line.combo_item_id
        if self.is_invoice(include_receipts=True) and combo_item and combo_item.product_quantity:
            base_line['quantity'] = product_line.quantity / combo_item.product_quantity

        return base_line

    def _post(self, soft=True):
        # Remove combo line sections before posting
        for move in self:
            if move.move_type in ('out_invoice', 'out_refund', 'in_invoice', 'in_refund'):
                move._process_combo_lines_before_post()

        return super(AccountMove, self)._post(soft=soft)

    def _process_combo_lines_before_post(self):
        """Remove combo line sections before posting
            - To Prevent Error When Creating Invoice for Subscription Combo Product
        """
        self.ensure_one()

        lines_to_remove = self.env['account.move.line']

        for line in self.invoice_line_ids:
            if line.display_type == 'line_section':
                next_lines = self.invoice_line_ids.filtered(
                    lambda l: l.sequence > line.sequence and l.display_type == 'product'
                ).sorted('sequence')

                # If the immediate next product lines have combo_item_id, this is likely a combo section
                if next_lines and any(next_lines[:3].mapped('combo_item_id')):
                    lines_to_remove |= line

        # Remove the identified combo sections
        if lines_to_remove:
            lines_to_remove.unlink()

    # def action_post(self):
    #     """Override to replace main combo product lines with section lines before posting
    #             - To Prevent Error When Creating Invoice for Subscription Combo Product
    #
    #     """
    #     for move in self:
    #         if move:
    #             move._process_combo_lines_before_post()
    #
    #     return super().action_post()
    #
    #
    # def _process_combo_lines_before_post(self):
    #     """Replace main combo product lines with section lines"""
    #
    #     lines_to_remove = self.env['account.move.line']
    #     combo_section_vals = []
    #
    #     for move in self:
    #         for line in move.invoice_line_ids:
    #             if line.display_type == 'line_section':
    #                 # Check if the next product lines after this section have combo_item_id
    #                 next_lines = move.invoice_line_ids.filtered(
    #                     lambda l: l.sequence > line.sequence and l.display_type == 'product'
    #                 ).sorted('sequence')
    #
    #                 # If the immediate next product lines have combo_item_id, this is likely a combo section
    #                 if next_lines and any(next_lines[:3].mapped('combo_item_id')):
    #                     combo_section_vals.append({
    #                         'name': line.name,
    #                         'sequence': line.sequence,
    #                         'move_id': move.id,
    #                     })
    #                     lines_to_remove |= line
    #
    #         # Remove the identified combo sections
    #         if lines_to_remove:
    #             lines_to_remove.unlink()
    #
    #     for vals in combo_section_vals:
    #         section_vals = {
    #             'display_type': 'line_section',
    #             'name': vals['name'],
    #             'sequence': vals['sequence'],
    #             'move_id': vals['move_id'],
    #         }
    #         _logger.info(section_vals)
    #
    #         self.env['account.move.line'].create(section_vals)
