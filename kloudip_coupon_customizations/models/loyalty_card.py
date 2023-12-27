# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class LoyaltyCard(models.Model):
    _inherit = 'loyalty.card'

    invoice_id = fields.Many2one('account.move', string='Invoice')
    credit_note_id = fields.Many2one('account.move', string='Credit Note', help='When refunded credit note will create for 1 quantity.')
    coupon_product_id = fields.Many2one('product.product', string='Coupon Product')
    # when adding coupons from sale order, we need to load coupons that are created for parent company also. so we
    # added new field to not disturb core functionality
    invoice_partner_id = fields.Many2one('res.partner', string='Partner',
                                         help='If the coupon created from invoice, this field will store invoice customer.')
    refunded_coupon = fields.Boolean(string='Refunded Coupon')
    sales_order_id = fields.Many2one('sale.order', string='Used in',
                                     help="The sales order on which the coupon is applied")
    initial_balance = fields.Float(string="Initial balance")
    state = fields.Selection([
        ('reserved', 'Pending'),
        ('new', 'Valid'),
        ('sent', 'Sent'),
        ('used', 'Used'),
        ('expired', 'Expired'),
        ('refunded', 'Refunded'),
        ('forfeited', 'Forfeited'),
        ('cancel', 'Cancelled')
    ], required=True, default='new')
    entry_id = fields.Many2one('account.move', string='Entry')

    def action_refund_coupon(self):
        journals = self.env['account.move'].browse(self.invoice_id.ids).journal_id.filtered(lambda x: x.active)
        # raise ValidationError(journals[0])
        """create credit note for assigned invoice id"""
        move_action = self.env['account.move.reversal'].with_context(active_id=self.invoice_id.id, active_ids=self.invoice_id.ids).create({
            'refund_method': 'refund',
            'move_ids': self.env['account.move'].browse(self.invoice_id.ids),
            'journal_id': journals[0].id if journals else None
        })
        reversal = move_action.reverse_moves()
        # find credit note from action
        credit_note = self.env['account.move'].browse(reversal['res_id'])
        move_lines = []
        to_remove_lines = credit_note.invoice_line_ids
        new_move = move_action.new_move_ids
        # invoice_line_ids = credit_note.invoice_line_ids.filtered(lambda x: not x.display_type and x.product_id.is_coupon_product)
        invoice_line_ids = credit_note.invoice_line_ids.filtered(lambda x: x.product_id.is_coupon_product)
        if len(invoice_line_ids) > 1:
            # TODO: Implement if needed
            _logger.info(invoice_line_ids.ids)
            raise ValidationError('Multiple coupon products found.')
        for line in invoice_line_ids:
            # remove unbalanced entry error pop up (check_move_validity=False)
            # line.with_context(check_move_validity=False).update({'quantity': 1.00})
            line.with_context(check_move_validity=False).write({'quantity': 1})
            to_remove_lines -= line
            # line_data = line.copy_data()[0]
            # line_data.update({'quantity': 1.00})
            # move_lines.append((0, 0, line_data))
        if to_remove_lines:
            to_remove_lines.with_context(check_move_validity=False).unlink()
        # credit_note.update({'invoice_line_ids': move_lines})
        new_move.with_context(**{'check_move_validity': False})._sync_dynamic_lines({'records': new_move})
        credit_note.action_post()

        # update necessary fields
        self.update({'refunded_coupon': True, 'credit_note_id': credit_note.id})
        return True

    def action_forfeited_coupon(self):
        journal = self.env['account.move']
        journals = journal.browse(self.invoice_id.ids).journal_id.filtered(lambda x: x.active)
        other_income_account_id = self.env['account.account'].search([('name', '=', 'Grant Income - KIP')])
        values = {
            'journal_id': journals.id,
            'move_type': 'entry',
            'line_ids': [
                (0, 0, {
                    'account_id': self.coupon_product_id.property_account_income_id.id,
                    'name': self.coupon_product_id.name + "Forfeited",
                    'debit': self.coupon_product_id.list_price,
                    'credit': 0
                }),
                (0, 0, {
                    'account_id': other_income_account_id.id if other_income_account_id else False,
                    'name': '',
                    'debit': 0,
                    'credit': self.coupon_product_id.list_price
                })
            ]
        }
        move = journal.create(values)
        move.action_post()
        self.write({'state': 'forfeited', 'entry_id': move.id})

    def name_get(self):
        """"Override name get for show coupon program name"""
        result = []
        for coupon in self:
            name = coupon.code + ' - ' + coupon.program_id.name
            result.append((coupon.id, name))
        return result