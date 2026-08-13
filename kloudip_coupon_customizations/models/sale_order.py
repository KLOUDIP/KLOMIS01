# -*- coding: utf-8 -*-
import itertools
from itertools import groupby
from collections import defaultdict

from odoo import api, fields, models, _, Command
from odoo.exceptions import AccessError, UserError
from odoo.tools.float_utils import float_is_zero


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    coupon_count = fields.Integer(string='Coupon Count', compute='_compute_coupon_count')
    generated_coupon_count = fields.Integer(string='Generated Coupon Count', compute='_compute_generated_coupon_count')
    forfeited_coupon_count = fields.Integer(string='Forfeited Coupon Count', compute='_compute_forfeited_coupon_count')

    def _get_account_for_line(self, line):
        """Helper to resolve the account_id for invoice lines to avoid constraint violations."""
        account = line.product_id.property_account_income_id or line.product_id.categ_id.property_account_income_categ_id
        if not account:
            account = line.order_id.partner_id.property_account_receivable_id
        return account

    def _create_invoices(self, grouped=False, final=False, date=None):
        """
        Enhanced override for Odoo 19 that ensures every invoice line
        receives a valid account_id.
        """
        refunded_amount = self.env.context.get('refunded_amount', 0)

        # 1) Generate moves using standard Odoo logic
        moves = super()._create_invoices(grouped=grouped, final=final, date=date)

        # 2) Force fix account_id for any line missing it
        for move in moves:
            for line in move.line_ids.filtered(lambda l: l.display_type == 'product' and not l.account_id):
                account = self._get_account_for_line(line)
                if account:
                    line.account_id = account.id
                else:
                    raise UserError(
                        _("Product %s is missing an Income Account. Please configure it in the Accounting tab.") % line.product_id.name)

        # 3) Apply custom coupon and refund logic
        for order in self:
            reward_line = order.order_line.filtered(lambda x: x.is_reward_line)
            product_line = order.order_line.filtered(
                lambda x: x.product_id.id in reward_line.reward_id.discount_product_ids.ids)

            credit_note_with_coupon = True if product_line.qty_to_invoice < 0 else False

            if final and credit_note_with_coupon:
                moves.with_context(credit_note_with_coupon=True).sudo().filtered(
                    lambda m: m.amount_total <= 0).action_switch_move_type()

            if refunded_amount > 0:
                refund_moves = []
                refund_move_vals = order._prepare_invoice()
                refund_move_vals.update({'refund_move': True})
                refund_line_vals = order.prepare_refunded_amount_line(product_line.qty_to_invoice, refunded_amount,
                                                                      reward_line, product_line)

                # Ensure refund lines also have accounts
                for line_val in refund_line_vals:
                    if not line_val.get('account_id'):
                        line_val['account_id'] = product_line.product_id.property_account_income_id.id

                refund_move_vals['invoice_line_ids'] = [Command.create(iv) for iv in refund_line_vals]
                refund_moves.append(refund_move_vals)

                refund_move = self.env['account.move'].sudo().with_context(default_move_type='out_invoice').create(
                    refund_moves)

                for rmove in refund_move:
                    rmove.message_post_with_source(
                        'mail.message_origin_link',
                        render_values={'self': rmove, 'origin': rmove.line_ids.mapped('sale_line_ids.order_id')},
                        subtype_xmlid='mail.mt_note'
                    )

        return moves

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
                return {'error': _('You can only add %s coupon%s for this sale order') % (int(product_qty), (
                    's' if product_qty > 1 else ''))}

        # handle refunded coupons
        if coupon.refunded_coupon:
            return {'error': _('This coupon is refunded (%s).') % (self.code)}
        elif len(order.order_line.filtered(
                lambda x: x.product_id.id in coupon.program_id.reward_ids.discount_product_ids.ids)) > 1:
            return {'error': _(
                'You can only add 1 order line with products in discount specific products (Coupon Program - %s)') % (
                                 self.program_id.name)}
        elif order.order_line.mapped('reward_id').id and order.order_line.mapped(
                'reward_id').id != coupon.program_id.id:
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
            'product_uom_id': reward_line.product_uom_id.id,
            'quantity': abs(qty),
            'discount': False,
            'price_unit': refunded_amount,
            'tax_ids': [(6, 0, reward_line.tax_ids.ids)],
            'analytic_distribution': reward_line.analytic_distribution,
            'sale_line_ids': [(4, reward_line.id)],
        }]

        if self.is_subscription:
            res[0].update(
                {'account_id': product_line.product_id.property_account_income_id.id if product_line else False})
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
            'context': {'default_visible_refunded_amount': bool(
                self.order_line.filtered(lambda x: x.qty_to_invoice < 0) and self.order_line.filtered(
                    lambda x: x.reward_id))}
        }

    def _compute_coupon_count(self):
        """
        Get the coupons count for the current sales order
        """
        self.update({
            'coupon_count': len(
                self.env['loyalty.card'].search([('sales_order_id', '=', self.id), ('state', '!=', 'forfeited')]).ids)
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
            'forfeited_coupon_count': len(
                self.env['loyalty.card'].search([('sales_order_id', '=', self.id), ('state', '=', 'forfeited')]).ids)
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
            action['view_mode'] = 'list,form'
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
            action['view_mode'] = 'list,form'
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
        coupon_ids = self.env['loyalty.card'].search(
            [('sales_order_id', '=', self.id), ('state', '=', 'forfeited')]).ids
        if len(coupon_ids) == 1:
            action['res_id'] = coupon_ids[0]
            action['view_mode'] = 'form'
        else:
            action['view_mode'] = 'list,form'
            action['domain'] = [('id', 'in', coupon_ids)]
        return action

    def create_voucher_deposit(self):
        if self.is_subscription:
            value = bool(self.order_line.filtered(lambda x: x.qty_to_invoice < 0) and self.order_line.filtered(
                lambda x: x.reward_id))
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
                cheapest_line = cheapest_line or self._cheapest_line(line_reward)
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
                discounted_amounts = defaultdict(int, {
                    sol.tax_ids.filtered(lambda t: t.amount_type != 'fixed'): abs(sol.price_total)
                    for sol in lines
                })
                for line in itertools.chain(non_common_lines, common_lines):
                    # For gift card and eWallet programs we have no tax but we can consume the amount completely
                    if lines.reward_id.program_id.is_payment_program:
                        discounted_amount = discounted_amounts[lines.tax_ids.filtered(lambda t: t.amount_type != 'fixed')]
                    else:
                        discounted_amount = discounted_amounts[line.tax_ids.filtered(lambda t: t.amount_type != 'fixed')]
                    if discounted_amount == 0:
                        continue
                    remaining = remaining_amount_per_line[line]
                    consumed = min(remaining, discounted_amount)
                    if lines.reward_id.program_id.is_payment_program:
                        discounted_amounts[lines.tax_ids.filtered(lambda t: t.amount_type != 'fixed')] -= consumed
                    else:
                        discounted_amounts[line.tax_ids.filtered(lambda t: t.amount_type != 'fixed')] -= consumed
                    remaining_amount_per_line[line] -= consumed

        discountable = 0
        discountable_per_tax = defaultdict(int)
        for line in lines_to_discount:
            discountable += remaining_amount_per_line[line]
            line_discountable = line.price_unit * line.product_uom_qty * (1 - (line.discount or 0.0) / 100.0)
            # line_discountable is the same as in a 'order' discount
            # but first multiplied by a factor for the taxes to apply
            # and then multiplied by another factor coming from the discountable
            taxes = line.tax_ids.filtered(lambda t: t.amount_type != 'fixed')
            discountable_per_tax[taxes] += line_discountable * (
                    remaining_amount_per_line[line] / line.price_total)

        return discountable, discountable_per_tax

    def action_invoice_subscription(self):
        value = bool(self.order_line.filtered(lambda x: x.qty_to_invoice < 0) and self.order_line.filtered(
            lambda x: x.reward_id))
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

    def _get_claimable_rewards(self, forced_coupons=None):
        self.ensure_one()
        all_coupons = forced_coupons or (
                self.coupon_point_ids.coupon_id | self.order_line.coupon_id | self.applied_coupon_ids)
        has_payment_reward = any(line.reward_id.program_id.is_payment_program for line in self.order_line)
        total_is_zero = float_is_zero(self.amount_total, precision_digits=2)
        result = defaultdict(lambda: self.env['loyalty.reward'])
        global_discount_reward = self._get_applied_global_discount()
        active_products_domain = self.env['loyalty.reward']._get_active_products_domain()

        for coupon in all_coupons:
            points = self._get_real_points_for_coupon(coupon)
            for reward in coupon.program_id.reward_ids:
                if reward.is_global_discount and global_discount_reward and global_discount_reward.discount >= reward.discount:
                    continue

                # Discounts are not allowed if the total is zero unless there is a payment reward, in which case we allow discounts.
                # If the total is 0 again without the payment reward it will be removed.
                is_discount = reward.reward_type == 'discount'
                is_payment_program = reward.program_id.is_payment_program
                if is_discount and total_is_zero and (not has_payment_reward or is_payment_program):
                    continue

                if reward.reward_type == 'product' and not reward.filtered_domain(active_products_domain):
                    continue

                if points >= reward.required_points:
                    result[coupon] |= reward

        return result