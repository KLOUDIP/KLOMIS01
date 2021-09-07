# -*- coding: utf-8 -*-

from itertools import groupby

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import float_is_zero
from odoo.addons.sale.models.sale import SaleOrder as SaleOrderBase
from odoo.addons.sale.models.sale import SaleOrderLine as SaleOrderLineBase


def _create_invoices(self, grouped=False, final=False, date=None):
    """
    Overload core method - Create the invoice associated to the SO.
    :param grouped: if True, invoices are grouped by SO id. If False, invoices are grouped by
                    (partner_invoice_id, currency)
    :param final: if True, refunds will be generated if necessary
    :returns: list of created invoices
    """
    if not self.env['account.move'].check_access_rights('create', False):
        try:
            self.check_access_rights('write')
            self.check_access_rule('write')
        except AccessError:
            return self.env['account.move']

    precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')

    # 1) Create invoices.
    invoice_vals_list = []
    invoice_item_sequence = 0
    refunded_amount = self.env.context.get('refunded_amount')
    refund_moves = []
    credit_note_with_coupon = False
    # lines_for_change_inv_status = []
    for order in self:
        order = order.with_company(order.company_id)
        current_section_vals = None
        down_payments = order.env['sale.order.line']

        # Invoice values.
        invoice_vals = order._prepare_invoice()

        # find product line for the coupon
        reward_line = order.order_line.filtered(lambda x: x.is_reward_line)
        product_line = order.order_line.filtered(lambda x: x.product_id.id in reward_line.coupon_program_id.discount_specific_product_ids.ids)

        # find current order create credit note with coupon
        credit_note_with_coupon = True if product_line.qty_to_invoice < 0 else False
        # lines_for_change_inv_status.append({'reward_line': reward_line, 'product_line': product_line})

        # Invoice line values (keep only necessary sections).
        invoice_lines_vals = []
        for line in order.order_line:
            # reward_invoice_line = False
            if line.display_type == 'line_section':
                current_section_vals = line._prepare_invoice_line(sequence=invoice_item_sequence + 1)
                continue
            if line.display_type != 'line_note' and float_is_zero(line.qty_to_invoice, precision_digits=precision):
                continue
                # # extend start
                # # adding coupon line when invoice creation for returned sale orders
                # if line.coupon_program_id and line.invoice_status == 'invoiced':
                #     reward_invoice_line = True
                #     invoice_qty = product_line.qty_to_invoice
                # else:
                #     continue
                # # extend end
            # if line.qty_to_invoice > 0 or (line.qty_to_invoice < 0 and final) or line.display_type == 'line_note' or reward_invoice_line:
            if line.qty_to_invoice > 0 or (line.qty_to_invoice < 0 and final) or line.display_type == 'line_note':
                if line.is_downpayment:
                    down_payments += line
                    continue
                if current_section_vals:
                    invoice_item_sequence += 1
                    invoice_lines_vals.append(current_section_vals)
                    current_section_vals = None
                invoice_item_sequence += 1
                prepared_line = line._prepare_invoice_line(sequence=invoice_item_sequence)
                # --
                # updating quantity of coupon line
                # if reward_invoice_line:
                #     prepared_line.update({
                #         'quantity': abs(invoice_qty),
                #         'price_unit': abs(prepared_line.get('price_unit', 0.00))
                #     })
                # --
                invoice_lines_vals.append(prepared_line)

        # If down payments are present in SO, group them under common section
        if down_payments:
            invoice_item_sequence += 1
            down_payments_section = order._prepare_down_payment_section_line(sequence=invoice_item_sequence)
            invoice_lines_vals.append(down_payments_section)
            for down_payment in down_payments:
                invoice_item_sequence += 1
                invoice_down_payment_vals = down_payment._prepare_invoice_line(sequence=invoice_item_sequence)
                invoice_lines_vals.append(invoice_down_payment_vals)

        if not any(new_line['display_type'] is False for new_line in invoice_lines_vals):
            raise self._nothing_to_invoice_error()

        invoice_vals['invoice_line_ids'] = [(0, 0, invoice_line_id) for invoice_line_id in invoice_lines_vals]

        invoice_vals_list.append(invoice_vals)

        # we needed to create an invoice with total value of refunded amount
        if refunded_amount > 0:
            refund_move_vals = order._prepare_invoice()
            refund_move_vals.update({'refund_move': True})
            refund_line_vals = order.prepare_refunded_amount_line(product_line.qty_to_invoice, refunded_amount, reward_line, product_line)
            refund_move_vals['invoice_line_ids'] = [(0, 0, invoice_line_id) for invoice_line_id in refund_line_vals]
            refund_moves.append(refund_move_vals)

    if not invoice_vals_list:
        raise self._nothing_to_invoice_error()

    # 2) Manage 'grouped' parameter: group by (partner_id, currency_id).
    if not grouped:
        new_invoice_vals_list = []
        invoice_grouping_keys = self._get_invoice_grouping_keys()
        for grouping_keys, invoices in groupby(invoice_vals_list, key=lambda x: [x.get(grouping_key) for grouping_key in
                                                                                 invoice_grouping_keys]):
            origins = set()
            payment_refs = set()
            refs = set()
            ref_invoice_vals = None
            for invoice_vals in invoices:
                if not ref_invoice_vals:
                    ref_invoice_vals = invoice_vals
                else:
                    ref_invoice_vals['invoice_line_ids'] += invoice_vals['invoice_line_ids']
                origins.add(invoice_vals['invoice_origin'])
                payment_refs.add(invoice_vals['payment_reference'])
                refs.add(invoice_vals['ref'])
            ref_invoice_vals.update({
                'ref': ', '.join(refs)[:2000],
                'invoice_origin': ', '.join(origins),
                'payment_reference': len(payment_refs) == 1 and payment_refs.pop() or False,
            })
            new_invoice_vals_list.append(ref_invoice_vals)
        invoice_vals_list = new_invoice_vals_list

    # 3) Create invoices.

    # As part of the invoice creation, we make sure the sequence of multiple SO do not interfere
    # in a single invoice. Example:
    # SO 1:
    # - Section A (sequence: 10)
    # - Product A (sequence: 11)
    # SO 2:
    # - Section B (sequence: 10)
    # - Product B (sequence: 11)
    #
    # If SO 1 & 2 are grouped in the same invoice, the result will be:
    # - Section A (sequence: 10)
    # - Section B (sequence: 10)
    # - Product A (sequence: 11)
    # - Product B (sequence: 11)
    #
    # Resequencing should be safe, however we resequence only if there are less invoices than
    # orders, meaning a grouping might have been done. This could also mean that only a part
    # of the selected SO are invoiceable, but resequencing in this case shouldn't be an issue.
    if len(invoice_vals_list) < len(self):
        SaleOrderLine = self.env['sale.order.line']
        for invoice in invoice_vals_list:
            sequence = 1
            for line in invoice['invoice_line_ids']:
                line[2]['sequence'] = SaleOrderLine._get_invoice_line_sequence(new=sequence, old=line[2]['sequence'])
                sequence += 1

    # Manage the creation of invoices in sudo because a salesperson must be able to generate an invoice from a
    # sale order without "billing" access rights. However, he should not be able to create an invoice from scratch.
    moves = self.env['account.move'].sudo().with_context(default_move_type='out_invoice').create(invoice_vals_list)

    # 4) Some moves might actually be refunds: convert them if the total amount is negative
    # We do this after the moves have been created since we need taxes, etc. to know if the total
    # is actually negative or not
    if final:
        if credit_note_with_coupon:
            moves.with_context(credit_note_with_coupon=True).sudo().filtered(lambda m: m.amount_total <= 0).action_switch_invoice_into_refund_credit_note()
        else:
            moves.sudo().filtered(lambda m: m.amount_total < 0).action_switch_invoice_into_refund_credit_note()
    for move in moves:
        move.message_post_with_view('mail.message_origin_link',
                                    values={'self': move, 'origin': move.line_ids.mapped('sale_line_ids.order_id')},
                                    subtype_id=self.env.ref('mail.mt_note').id
                                    )

    # generate move for refunded amount
    if refunded_amount > 0:
        refund_move = self.env['account.move'].sudo().with_context(default_move_type='out_invoice').create(refund_moves)
        # post message with origin
        for move in refund_move:
            move.message_post_with_view('mail.message_origin_link',
                                        values={'self': move, 'origin': move.line_ids.mapped('sale_line_ids.order_id')},
                                        subtype_id=self.env.ref('mail.mt_note').id
                                        )

    return moves


SaleOrderBase._create_invoices = _create_invoices


@api.depends(
        'qty_invoiced',
        'qty_delivered',
        'product_uom_qty',
        'order_id.state',
        'product_id.invoice_policy')
def _get_to_invoice_qty(self):
    """
    Override core method - Compute the quantity to invoice. If the invoice policy is order, the quantity to invoice is
    calculated from the ordered quantity. Otherwise, the quantity delivered is used.
    """
    for line in self:
        if line.order_id.state in ['sale', 'done']:
            if line.product_id.invoice_policy == 'order':
                line.qty_to_invoice = line.product_uom_qty - line.qty_invoiced
            else:
                line.qty_to_invoice = line.qty_delivered - line.qty_invoiced
        else:
            line.qty_to_invoice = 0
        # extends here
        reward_line = line.order_id.order_line.filtered(lambda x: x.is_reward_line)
        product_line = line.order_id.order_line.filtered(lambda x: x.product_id.id in reward_line.coupon_program_id.discount_specific_product_ids.ids)
        if (reward_line and (line.product_id.id in reward_line.coupon_program_id.discount_specific_product_ids.ids)) or (line.product_id.id == reward_line.coupon_program_id.discount_line_product_id.id):  # FIXME: Only for Specific line
            # reward_line.qty_to_invoice = line.qty_delivered - line.qty_invoiced
            reward_line.qty_to_invoice = product_line.qty_delivered - product_line.qty_invoiced


SaleOrderLineBase._get_to_invoice_qty = _get_to_invoice_qty


@api.depends('invoice_lines.move_id.state', 'invoice_lines.quantity', 'untaxed_amount_to_invoice')
def _get_invoice_qty(self):
    """
    Override core method - Compute the quantity invoiced. If case of a refund, the quantity invoiced is decreased. Note
    that this is the case only if the refund is generated from the SO and that is intentional: if
    a refund made would automatically decrease the invoiced quantity, then there is a risk of reinvoicing
    it automatically, which may not be wanted at all. That's why the refund has to be created from the SO
    """
    for line in self:
        qty_invoiced = 0.0
        invoice_lines = line.invoice_lines.filtered(lambda x: not x.move_id.refund_move)  # extended line
        for invoice_line in invoice_lines:
            if invoice_line.move_id.state != 'cancel':
                if invoice_line.move_id.move_type == 'out_invoice':
                    qty_invoiced += invoice_line.product_uom_id._compute_quantity(invoice_line.quantity, line.product_uom)
                elif invoice_line.move_id.move_type == 'out_refund':
                    if not line.is_downpayment or line.untaxed_amount_to_invoice == 0 :
                        qty_invoiced -= invoice_line.product_uom_id._compute_quantity(invoice_line.quantity, line.product_uom)
        line.qty_invoiced = qty_invoiced


SaleOrderLineBase._get_invoice_qty = _get_invoice_qty


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # we needed to show refunded_amount field in payment advance wizard if the sale order line have negative invoice
    # amount and coupon assigned so we created a compute field for find out
    visible_refunded_amount = fields.Boolean(string='Visible Refunded Amount', help='For UI Purposes', compute='_visible_refunded_amount_field')

    @api.depends('order_line', 'order_line.qty_to_invoice')
    def _visible_refunded_amount_field(self):
        self.update({
            'visible_refunded_amount': self.order_line.filtered(lambda x: x.qty_to_invoice < 0) and self.order_line.filtered(lambda x: x.coupon_program_id)
        })

    def prepare_refunded_amount_line(self, qty, refunded_amount, reward_line, product_line):
        """Create line values for refunded amount move
        :param qty: float quantity to invoice
        :param refunded_amount: refunded amount value
        :param reward_line: reward line for the refunded value
        :param product_line: product line that belongs to reward line
        """
        self.ensure_one()
        res = [{
            'display_type': False,
            'sequence': reward_line.sequence,
            'name': product_line.name + ' - Refunded Amount',
            'product_id': False,
            'product_uom_id': reward_line.product_uom.id,
            'quantity': abs(qty),
            'discount': False,
            'price_unit': refunded_amount,
            'tax_ids': [(6, 0, reward_line.tax_id.ids)],
            'analytic_account_id': self.analytic_account_id.id,
            'analytic_tag_ids': [(6, 0, reward_line.analytic_tag_ids.ids)],
            'sale_line_ids': [(4, reward_line.id)],
        }]
        return res

    def sale_coupon_apply_code_action(self):
        return {
            'name': _("Enter Promotion or Coupon Code"),
            'view_mode': 'form',
            'view_id': self.env.ref('sale_coupon.sale_coupon_apply_code_view_form').id,
            'res_model': 'sale.coupon.apply.code',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'domain': [],
            'context': {'default_partner_id': self.partner_id.id}
        }