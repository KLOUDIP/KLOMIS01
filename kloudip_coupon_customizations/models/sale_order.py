# -*- coding: utf-8 -*-
import itertools
from itertools import groupby

from odoo import api, fields, models, _, Command
from odoo.exceptions import AccessError, ValidationError, UserError
from odoo.addons.sale.models.sale_order import SaleOrder as SaleOrderBase
from odoo.addons.sale.models.sale_order_line import SaleOrderLine as SaleOrderLineBase
from collections import defaultdict


def _create_invoices(self, grouped=False, final=False, date=None):
        """ Create invoice(s) for the given Sales Order(s).

        :param bool grouped: if True, invoices are grouped by SO id.
            If False, invoices are grouped by keys returned by :meth:`_get_invoice_grouping_keys`
        :param bool final: if True, refunds will be generated if necessary
        :param date: unused parameter
        :returns: created invoices
        :rtype: `account.move` recordset
        :raises: UserError if one of the orders has no invoiceable lines.
        """
        if not self.env['account.move'].check_access_rights('create', False):
            try:
                self.check_access_rights('write')
                self.check_access_rule('write')
            except AccessError:
                return self.env['account.move']

        deduct_down_payments = self.env.context.get('deduct_down_payments')
        if deduct_down_payments:
            final = True

        # 1) Create invoices.
        invoice_vals_list = []
        # Extended content
        refunded_amount = self.env.context.get('refunded_amount')
        refund_moves = []
        credit_note_with_coupon = False
        # ====
        invoice_item_sequence = 0 # Incremental sequencing to keep the lines order on the invoice.
        for order in self:
            order = order.with_company(order.company_id).with_context(lang=order.partner_invoice_id.lang)
            # find product line for the coupon
            reward_line = self.order_line.filtered(lambda x: x.is_reward_line)  # Extended line
            product_line = self.order_line.filtered(
                lambda x: x.product_id.id in reward_line.reward_id.discount_product_ids.ids)  # Extended line

            # find current order create credit note with coupon
            credit_note_with_coupon = True if product_line.qty_to_invoice < 0 else False  # Extended line

            invoice_vals = order._prepare_invoice()
            invoiceable_lines = order._get_invoiceable_lines(final)

            connection = invoiceable_lines.filtered(lambda x: x.product_id.categ_id.name == '2-Connections')
            voucher_deposit = self.env.context.get('create_voucher_deposit')
            if voucher_deposit:
                new_list = invoiceable_lines.filtered(
                    lambda x: x.id in product_line.ids or x.id in reward_line.ids or x.id in connection.ids)
                invoiceable_lines = new_list

            if not any(not line.display_type for line in invoiceable_lines):
                continue

            invoice_line_vals = []
            down_payment_section_added = False
            for line in invoiceable_lines:
                if not down_payment_section_added and line.is_downpayment:
                    # Create a dedicated section for the down payments
                    # (put at the end of the invoiceable_lines)
                    invoice_line_vals.append(
                        Command.create(
                            order._prepare_down_payment_section_line(sequence=invoice_item_sequence)
                        ),
                    )
                    down_payment_section_added = True
                    invoice_item_sequence += 1
                invoice_line_vals.append(
                    Command.create(
                        line._prepare_invoice_line(sequence=invoice_item_sequence)
                    ),
                )
                invoice_item_sequence += 1

            invoice_vals['invoice_line_ids'] += invoice_line_vals
            invoice_vals_list.append(invoice_vals)

            # Extended content start
            # we needed to create an invoice with total value of refunded amount
            if refunded_amount > 0:
                refund_move_vals = order._prepare_invoice()
                refund_move_vals.update({'refund_move': True})
                refund_line_vals = order.prepare_refunded_amount_line(product_line.qty_to_invoice, refunded_amount,
                                                                      reward_line, product_line)
                refund_move_vals['invoice_line_ids'] = [(0, 0, invoice_line_id) for invoice_line_id in refund_line_vals]
                refund_moves.append(refund_move_vals)
            # Extended content end

        if not invoice_vals_list and self._context.get('raise_if_nothing_to_invoice', True):
            raise UserError(self._nothing_to_invoice_error_message())

        # 2) Manage 'grouped' parameter: group by (partner_id, currency_id).
        if not grouped:
            new_invoice_vals_list = []
            invoice_grouping_keys = self._get_invoice_grouping_keys()
            invoice_vals_list = sorted(
                invoice_vals_list,
                key=lambda x: [
                    x.get(grouping_key) for grouping_key in invoice_grouping_keys
                ]
            )
            for _grouping_keys, invoices in groupby(invoice_vals_list, key=lambda x: [x.get(grouping_key) for grouping_key in invoice_grouping_keys]):
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
                moves.with_context(credit_note_with_coupon=True).sudo().filtered(lambda m: m.amount_total <= 0).action_switch_move_type()
            else:  # End extended content
                moves.sudo().filtered(lambda m: m.amount_total < 0).action_switch_move_type()
        for move in moves:
            if final:
                # Downpayment might have been determined by a fixed amount set by the user.
                # This amount is tax included. This can lead to rounding issues.
                # E.g. a user wants a 100€ DP on a product with 21% tax.
                # 100 / 1.21 = 82.64, 82.64 * 1,21 = 99.99
                # This is already corrected by adding/removing the missing cents on the DP invoice,
                # but must also be accounted for on the final invoice.

                delta_amount = 0
                for order_line in self.order_line:
                    if not order_line.is_downpayment:
                        continue
                    inv_amt = order_amt = 0
                    for invoice_line in order_line.invoice_lines:
                        if invoice_line.move_id == move:
                            inv_amt += invoice_line.price_total
                        elif invoice_line.move_id.state != 'cancel':  # filter out canceled dp lines
                            order_amt += invoice_line.price_total
                    if inv_amt and order_amt:
                        # if not inv_amt, this order line is not related to current move
                        # if no order_amt, dp order line was not invoiced
                        delta_amount += (inv_amt * (1 if move.is_inbound() else -1)) + order_amt

                if not move.currency_id.is_zero(delta_amount):
                    receivable_line = move.line_ids.filtered(
                        lambda aml: aml.account_id.account_type == 'asset_receivable')[:1]
                    product_lines = move.line_ids.filtered(
                        lambda aml: aml.display_type == 'product' and aml.is_downpayment)
                    tax_lines = move.line_ids.filtered(
                        lambda aml: aml.tax_line_id.amount_type not in (False, 'fixed'))
                    if tax_lines and product_lines and receivable_line:
                        line_commands = [Command.update(receivable_line.id, {
                            'amount_currency': receivable_line.amount_currency + delta_amount,
                        })]
                        delta_sign = 1 if delta_amount > 0 else -1
                        for lines, attr, sign in (
                            (product_lines, 'price_total', -1 if move.is_inbound() else 1),
                            (tax_lines, 'amount_currency', 1),
                        ):
                            remaining = delta_amount
                            lines_len = len(lines)
                            for line in lines:
                                if move.currency_id.compare_amounts(remaining, 0) != delta_sign:
                                    break
                                amt = delta_sign * max(
                                    move.currency_id.rounding,
                                    abs(move.currency_id.round(remaining / lines_len)),
                                )
                                remaining -= amt
                                line_commands.append(Command.update(line.id, {attr: line[attr] + amt * sign}))
                        move.line_ids = line_commands

            move.message_post_with_source(
                'mail.message_origin_link',
                render_values={'self': move, 'origin': move.line_ids.sale_line_ids.order_id},
                subtype_xmlid='mail.mt_note',
            )
            # Extended content start
            # generate move for refunded amount
            if refunded_amount > 0:
                refund_move = self.env['account.move'].sudo().with_context(default_move_type='out_invoice').create(
                    refund_moves)
                # post message with origin
                for rmove in refund_move:
                    rmove.message_post_with_source(
                        'mail.message_origin_link',
                        render_values={'self': rmove, 'origin': rmove.line_ids.mapped('sale_line_ids.order_id')},
                        subtype_xmlid='mail.mt_note'
                    )
        return moves


SaleOrderBase._create_invoices = _create_invoices


@api.depends('qty_invoiced', 'qty_delivered', 'product_uom_qty', 'state')
def _compute_qty_to_invoice(self):
    """
    @override
    Compute the quantity to invoice. If the invoice policy is order, the quantity to invoice is
    calculated from the ordered quantity. Otherwise, the quantity delivered is used.
    """
    for line in self:
        if line.state == 'sale' and not line.display_type:
            if line.product_id.invoice_policy == 'order':
                line.qty_to_invoice = line.product_uom_qty - line.qty_invoiced
            else:
                line.qty_to_invoice = line.qty_delivered - line.qty_invoiced
        else:
            line.qty_to_invoice = 0
        # extends here
        reward_line = line.order_id.order_line.filtered(lambda x: x.is_reward_line)
        product_line = line.order_id.order_line.filtered(lambda x: x.product_id.id in reward_line.reward_id.discount_product_ids.ids)
        if (reward_line and (line.product_id.id in reward_line.reward_id.discount_product_ids.ids)) or (line.product_id.id == reward_line.reward_id.discount_line_product_id.id):  # FIXME: Only for Specific line
            # reward_line.qty_to_invoice = line.qty_delivered - line.qty_invoiced
            reward_line.qty_to_invoice = product_line.qty_delivered - product_line.qty_invoiced


SaleOrderLineBase._compute_qty_to_invoice = _compute_qty_to_invoice


@api.depends('invoice_lines.move_id.state', 'invoice_lines.quantity')
def _compute_qty_invoiced(self):
    """
    @override
    Compute the quantity invoiced. If case of a refund, the quantity invoiced is decreased. Note
    that this is the case only if the refund is generated from the SO and that is intentional: if
    a refund made would automatically decrease the invoiced quantity, then there is a risk of reinvoicing
    it automatically, which may not be wanted at all. That's why the refund has to be created from the SO
    """
    for line in self:
        qty_invoiced = 0.0
        # Extend start
        invoice_lines = line._get_invoice_lines()
        invoice_lines = invoice_lines.filtered(lambda x: not x.move_id.refund_move)
        for invoice_line in invoice_lines:
            if invoice_line.move_id.state != 'cancel' or invoice_line.move_id.payment_state == 'invoicing_legacy':
                if invoice_line.move_id.move_type == 'out_invoice':
                    qty_invoiced += invoice_line.product_uom_id._compute_quantity(invoice_line.quantity,
                                                                                  line.product_uom)
                elif invoice_line.move_id.move_type == 'out_refund':
                    qty_invoiced -= invoice_line.product_uom_id._compute_quantity(invoice_line.quantity,
                                                                                  line.product_uom)
        line.qty_invoiced = qty_invoiced


SaleOrderLineBase._compute_qty_invoiced = _compute_qty_invoiced


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    coupon_count = fields.Integer(string='Coupon Count', compute='_compute_coupon_count')
    generated_coupon_count = fields.Integer(string='Generated Coupon Count', compute='_compute_generated_coupon_count')
    forfeited_coupon_count = fields.Integer(string='Forfeited Coupon Count', compute='_compute_forfeited_coupon_count')

    def _check_multiple_coupons_status(self, coupon):
        """
        @private - handle multiple coupons
        """
        order = self
        if coupon and coupon.program_id.allow_redeem_multiple_coupons:
            order_lines = order.order_line.filtered(lambda x: (x.display_type not in ('line_section', 'line_note')))
            product_qty = sum(order_lines.filtered(lambda x: x.price_unit > 0).mapped('product_uom_qty'))
            discount_qty = sum(order_lines.filtered(lambda x: x.price_unit < 0).mapped('product_uom_qty'))
            if product_qty == discount_qty:
                return {'error': _('You can only add %s coupon%s for this sale order') % (int(product_qty), ('s' if product_qty > 1 else ''))}
        # handle refunded coupons
        if coupon.refunded_coupon:
            return {'error': _('This coupon is refunded (%s).') % (self.code)}
        elif len(order.order_line.filtered(lambda x: x.product_id.id in coupon.program_id.reward_ids.discount_product_ids.ids)) > 1:
            return {'error': _('You can only add 1 order line with products in discount specific products (Coupon Program - %s)') % (self.program_id.name)}
        # elif len(order.order_line.mapped('coupon_program_id')) > 0:
        #     message = {'error': _('You can only add 1 coupon program to a sale order!')}
        elif order.order_line.mapped('reward_id').id and order.order_line.mapped('reward_id').id != coupon.program_id.id:
            return {'error': _('You can only add 1 coupon program to a sale order!')}

    def prepare_refunded_amount_line(self, qty, refunded_amount, reward_line, product_line):
        """Create line values for refunded amount move
        :param qty: float quantity to invoice
        :param refunded_amount: refunded amount value
        :param reward_line: reward line for the refunded value
        :param product_line: product line that belongs to reward line
        """
        self.ensure_one()
        res = [{
            'display_type': 'product',
            'sequence': reward_line.sequence,
            'name': (product_line.name or '') + ' - Refunded Amount',
            'product_id': False,
            'product_uom_id': reward_line.product_uom.id,
            'quantity': abs(qty),
            'discount': False,
            'price_unit': refunded_amount,
            'tax_ids': [(6, 0, reward_line.tax_id.ids)],
            'analytic_distribution': self.analytic_account_id.id,
            'sale_line_ids': [(4, reward_line.id)],
        }]
        if self.is_subscription:
            res[0].update({'account_id': product_line.product_id.property_account_income_id.id if product_line else False})
        return res

    def action_open_sale_loyalty_coupon_wizard(self):
        """
        @public - Action for open sale loyalty coupon wizard
        """
        return {
            'name': _("Enter Promotion or Coupon Code"),
            'view_mode': 'form',
            'view_id': self.env.ref('sale_loyalty.sale_loyalty_coupon_wizard_view_form').id,
            'res_model': 'sale.loyalty.coupon.wizard',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'domain': [],
            'context': {'default_partner_id': self.partner_invoice_id.id}
        }

    def action_open_sale_make_invoice_advance_wizard(self):
        """Open sale_make_invoice_advance_wizard"""
        return {
            'name': _("Create invoices"),
            'view_mode': 'form',
            'res_model': 'sale.advance.payment.inv',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'domain': [],
            # We needed to show refunded_amount field in payment advance wizard if the sale order line have
            # negative invoice
            'context': {'default_visible_refunded_amount': bool(self.order_line.filtered(lambda x: x.qty_to_invoice < 0) and self.order_line.filtered(lambda x: x.reward_id))}
        }

    def _compute_coupon_count(self):
        """
        Get the coupons count for the current sales order
        """
        self.update({
            'coupon_count': len(self.env['loyalty.card'].search([('sales_order_id', '=', self.id), ('state', '!=', 'forfeited')]).ids)
        })

    def _compute_generated_coupon_count(self):
        """
        Get the coupons count for the current sales order
        """
        self.update({
            'generated_coupon_count': len(self.env['loyalty.card'].search([('order_id', '=', self.id)]).ids)
        })

    def _compute_forfeited_coupon_count(self):
        self.update({
            'forfeited_coupon_count': len(self.env['loyalty.card'].search([('sales_order_id', '=', self.id), ('state', '=', 'forfeited')]).ids)
        })

    def action_view_assigned_coupons(self):
        """
        Action for view assigned coupons for the current sales order
        """
        action = {
            'name': _('Coupon(s)'),
            'type': 'ir.actions.act_window',
            'res_model': 'loyalty.card',
            'target': 'current',
        }
        coupon_ids = self.env['loyalty.card'].search([('sales_order_id', '=', self.id)]).ids
        if len(coupon_ids) == 1:
            action['res_id'] = coupon_ids[0]
            action['view_mode'] = 'form'
        else:
            action['view_mode'] = 'tree,form'
            action['domain'] = [('id', 'in', coupon_ids)]
        return action

    def action_view_generated_coupons(self):
        """
        Action for view generated coupons for the current sales order
        """
        action = {
            'name': _('Coupon(s)'),
            'type': 'ir.actions.act_window',
            'res_model': 'loyalty.card',
            'target': 'current',
        }
        coupon_ids = self.env['loyalty.card'].search([('order_id', '=', self.id)]).ids
        if len(coupon_ids) == 1:
            action['res_id'] = coupon_ids[0]
            action['view_mode'] = 'form'
        else:
            action['view_mode'] = 'tree,form'
            action['domain'] = [('id', 'in', coupon_ids)]
        return action

    def action_view_forfeited_coupons(self):
        """
        Action for view forfeited coupons for the current sales order
        """
        action = {
            'name': _('Vouchers(s)'),
            'type': 'ir.actions.act_window',
            'res_model': 'loyalty.card',
            'target': 'current',
        }
        coupon_ids = self.env['loyalty.card'].search([('sales_order_id', '=', self.id), ('state', '=', 'forfeited')]).ids
        if len(coupon_ids) == 1:
            action['res_id'] = coupon_ids[0]
            action['view_mode'] = 'form'
        else:
            action['view_mode'] = 'tree,form'
            action['domain'] = [('id', 'in', coupon_ids)]
        return action

    def create_voucher_deposit(self):
        if self.is_subscription:
            value = bool(self.order_line.filtered(lambda x: x.qty_to_invoice < 0) and self.order_line.filtered(lambda x: x.reward_id))
            if not value:
                account_move = self.with_context(refunded_amount=0)._create_recurring_invoice()
                if account_move:
                    return self.action_view_invoice()
                else:
                    raise UserError(self._nothing_to_invoice_error_message())
            return {
                'name': _('Subscription Invoice'),
                'view_mode': 'form',
                'view_id': self.env.ref('kloudip_coupon_customizations.view_subscription_advance_payment_inv').id,
                'res_model': 'subscription.advance.payment.inv',
                'target': 'new',
                'context': {'create_voucher_deposit': True},
                'type': 'ir.actions.act_window',
            }
        else:
            return self.with_context(create_voucher_deposit=True).action_open_sale_make_invoice_advance_wizard()

    def __try_apply_program(self, program, coupon, status):
        coupons = super(SaleOrder, self).__try_apply_program(program, coupon, status)
        if 'coupon' in coupons:
            for rec in coupons['coupon']:
                rec.invoice_partner_id = self.partner_invoice_id.id
                rec.points = 1
        return coupons

    def _try_apply_program(self, program, coupon=None):

        self.ensure_one()
        # Basic checks
        if not program.filtered_domain(self._get_program_domain()):
            return {'error': _('The program is not available for this order.')}

        if not program.allow_redeem_multiple_coupons:
            if program in self._get_applied_programs():
                return {'error': _('This program is already applied to this order.')}
        # Check for applicability from the program's triggers/rules.
        # This step should also compute the amount of points to give for that program on that order.
        status = self._program_check_compute_points(program)[program]
        if 'error' in status:
            return status
        return self.__try_apply_program(program, coupon, status)

    def _write_vals_from_reward_vals(self, reward_vals, old_lines, delete=True):
        """
        Update, create new reward line and delete old lines in one write on `order_line`

        Returns the untouched old lines.
        """
        self.ensure_one()
        product_ids = list(map(lambda x: x['product_id'], reward_vals))
        command_list = []
        if not old_lines:
            old_lines = self.order_line.filtered(lambda x: x.product_id.id in product_ids)
            qty = old_lines.product_uom_qty if old_lines else 1
        else:
            qty = old_lines.product_uom_qty
        if self.order_line.reward_id.program_id.allow_redeem_multiple_coupons:
            if not old_lines.coupon_id.id in list(map(lambda x: x['coupon_id'], reward_vals)):
                if product_ids:
                    qty = ((old_lines.product_uom_qty if old_lines else 0) + 1)

        for vals, line in zip(reward_vals, old_lines):
            vals.update({'product_uom_qty': qty})
            command_list.append((Command.UPDATE, line.id, vals))
        if len(reward_vals) > len(old_lines):
            command_list.extend((Command.CREATE, 0, vals) for vals in reward_vals[len(old_lines):])
        elif len(reward_vals) < len(old_lines) and delete:
            command_list.extend((Command.DELETE, line.id) for line in old_lines[len(reward_vals):])
        self.write({'order_line': command_list})
        order_ln = self.order_line.filtered(lambda x: x.is_reward_line)
        if order_ln:
            order_ln.coupon_id.write({'state': 'used', 'sales_order_id': self.id})

        return self.env['sale.order.line'] if delete else old_lines[len(reward_vals):]

    def _discountable_specific(self, reward):
        """
        Special function to compute the discountable for 'specific' types of discount.
        The goal of this function is to make sure that applying a 5$ discount on an order with a
         5$ product and a 5% discount does not make the order go below 0.

        Returns the discountable and discountable_per_tax for a discount that only applies to specific products.
        """
        self.ensure_one()
        assert reward.discount_applicability == 'specific'

        lines_to_discount = self.env['sale.order.line']
        discount_lines = defaultdict(lambda: self.env['sale.order.line'])
        order_lines = self.order_line - self._get_no_effect_on_threshold_lines()
        remaining_amount_per_line = defaultdict(int)
        for line in order_lines:
            if not line.product_uom_qty or not line.price_unit:
                continue
            remaining_amount_per_line[line] = line.price_total
            domain = reward._get_discount_product_domain()
            if not line.reward_id and line.product_id.filtered_domain(domain):
                lines_to_discount |= line
            elif line.reward_id.reward_type == 'discount':
                discount_lines[line.reward_identifier_code] |= line

        order_lines -= self.order_line.filtered("reward_id")
        cheapest_line = False
        for lines in discount_lines.values():
            line_reward = lines.reward_id
            discounted_lines = order_lines
            if line_reward.discount_applicability == 'cheapest':
                cheapest_line = cheapest_line or self._cheapest_line()
                discounted_lines = cheapest_line
            elif line_reward.discount_applicability == 'specific':
                discounted_lines = self._get_specific_discountable_lines(line_reward)
            if not discounted_lines:
                continue
            common_lines = discounted_lines & lines_to_discount
            if line_reward.discount_mode == 'percent':
                for line in discounted_lines:
                    if line_reward.discount_applicability == 'cheapest':
                        remaining_amount_per_line[line] *= (1 - line_reward.discount / 100 / line.product_uom_qty)
                    else:
                        remaining_amount_per_line[line] *= (1 - line_reward.discount / 100 / line.product_uom_qty)
            else:
                non_common_lines = discounted_lines - lines_to_discount
                # Fixed prices are per tax
                discounted_amounts = {line.tax_id: abs(line.price_total) for line in lines}
                for line in itertools.chain(non_common_lines, common_lines):
                    # For gift card and eWallet programs we have no tax but we can consume the amount completely
                    if lines.reward_id.program_id.is_payment_program:
                        discounted_amount = discounted_amounts[lines.tax_id]
                    else:
                        discounted_amount = discounted_amounts[line.tax_id]
                    if discounted_amount == 0:
                        continue
                    remaining = remaining_amount_per_line[line]
                    consumed = min(remaining, discounted_amount)
                    if lines.reward_id.program_id.is_payment_program:
                        discounted_amounts[lines.tax_id] -= consumed
                    else:
                        discounted_amounts[line.tax_id] -= consumed
                    remaining_amount_per_line[line] -= consumed

        discountable = 0
        discountable_per_tax = defaultdict(int)
        for line in lines_to_discount:
            discountable += remaining_amount_per_line[line]
            line_discountable = line.price_unit * line.product_uom_qty * (1 - (line.discount or 0.0) / 100.0)
            # line_discountable is the same as in a 'order' discount
            #  but first multiplied by a factor for the taxes to apply
            #  and then multiplied by another factor coming from the discountable
            discountable_per_tax[line.tax_id] += line_discountable * \
                                                 (remaining_amount_per_line[line] / line.price_total)
        return discountable, discountable_per_tax

    def action_invoice_subscription(self):
        value = bool(self.order_line.filtered(lambda x: x.qty_to_invoice < 0) and self.order_line.filtered(lambda x: x.reward_id))
        if not value:
            account_move = self.with_context(refunded_amount=0)._create_recurring_invoice()
            if account_move:
                return self.action_view_invoice()
            else:
                raise UserError(self._nothing_to_invoice_error_message())
        return {
            'name': _('Subscription Invoice'),
            'view_mode': 'form',
            'view_id': self.env.ref('kloudip_coupon_customizations.view_subscription_advance_payment_inv').id,
            'res_model': 'subscription.advance.payment.inv',
            'target': 'new',
            'type': 'ir.actions.act_window',
        }

    def _get_real_points_for_coupon(self, coupon, post_confirm=False):
        """
        Returns the actual points usable for this coupon for this order. Set pos_confirm to True to include points for future orders.

        This is calculated by taking the points on the coupon, the points the order will give to the coupon (if applicable) and removing the points taken by already applied rewards.
        """
        self.ensure_one()
        points = coupon.points
        if (coupon.program_id.applies_on != 'future' and self.state not in ('sale', 'done')) or post_confirm:
            # Points that will be given by the order upon confirming the order
            points += self.coupon_point_ids.filtered(lambda p: p.coupon_id == coupon).points
        # Points already used by rewards
        if self.order_line.filtered(lambda l: l.coupon_id == coupon):
            points -= sum(self.order_line.filtered(lambda l: l.coupon_id == coupon).mapped('points_cost'))
        else:
            if coupon.state == 'used':
                points -= 1
        points = coupon.currency_id.round(points)
        return points


