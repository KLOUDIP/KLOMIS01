import logging

from odoo import models

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _prepare_product_base_line_for_taxes_computation(self, product_line):
        """ Convert an account.move.line having display_type='product' into a base line for the taxes computation.

        :param product_line: An account.move.line.
        :return: A base line returned by '_prepare_base_line_for_taxes_computation'.
        """
        self.ensure_one()
        is_invoice = self.is_invoice(include_receipts=True)
        sign = self.direction_sign if is_invoice else 1
        if is_invoice:
            rate = self.invoice_currency_rate
        else:
            rate = (abs(product_line.amount_currency) / abs(product_line.balance)) if product_line.balance else 0.0
        if product_line.combo_item_id:
            return self.env['account.tax']._prepare_base_line_for_taxes_computation(
                product_line,
                price_unit=product_line.price_unit if is_invoice else product_line.amount_currency,
                quantity=product_line.quantity / product_line.combo_item_id.product_quantity or 1.0,
                discount=product_line.discount if is_invoice else 0.0,
                rate=rate,
                sign=sign,
                special_mode=False if is_invoice else 'total_excluded',
            )
        else:
            return self.env['account.tax']._prepare_base_line_for_taxes_computation(
                product_line,
                price_unit=product_line.price_unit if is_invoice else product_line.amount_currency,
                quantity=product_line.quantity if is_invoice else 1.0,
                discount=product_line.discount if is_invoice else 0.0,
                rate=rate,
                sign=sign,
                special_mode=False if is_invoice else 'total_excluded',
            )

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
