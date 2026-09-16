# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    is_internal_transfer = fields.Boolean(
        string='Internal Transfer',
        tracking=True,
    )
    destination_journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Destination Journal',
        domain="[('type', 'in', ('bank', 'cash')), ('company_id', '=', company_id), ('id', '!=', journal_id)]",
        check_company=True,
        tracking=True,
    )

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        if self.env.context.get('default_is_internal_transfer'):
            company = self.env.company
            vals.update({
                'is_internal_transfer': True,
                'partner_id': company.partner_id.id,
                'partner_type': 'customer',
                'payment_type': vals.get('payment_type') or 'outbound',
            })
        return vals

    @api.constrains('is_internal_transfer', 'destination_journal_id', 'journal_id', 'company_id')
    def _check_internal_transfer_configuration(self):
        for payment in self.filtered('is_internal_transfer'):
            if not payment.destination_journal_id:
                raise ValidationError(_("Destination journal is required for internal transfers."))
            if payment.destination_journal_id == payment.journal_id:
                raise ValidationError(_("Source and destination journals must be different."))
            if not payment.company_id.transfer_account_id:
                raise ValidationError(_(
                    "Configure an Internal Transfer account under "
                    "Accounting -> Configuration -> Settings."
                ))

    @api.onchange('is_internal_transfer', 'destination_journal_id')
    def _onchange_internal_transfer_partner(self):
        for payment in self:
            if payment.is_internal_transfer:
                payment.partner_id = payment.company_id.partner_id
                if not payment.paired_internal_transfer_payment_id:
                    payment.payment_type = 'outbound'
                payment._set_default_payment_method_line()
            elif payment.partner_id == payment.company_id.partner_id:
                payment.partner_id = False

    @api.onchange('journal_id', 'payment_type')
    def _onchange_journal_payment_method_line(self):
        for payment in self:
            if payment.journal_id:
                payment._set_default_payment_method_line()

    def _set_default_payment_method_line(self):
        for payment in self:
            available_lines = payment.journal_id._get_available_payment_method_lines(
                payment.payment_type,
            )
            if payment.payment_method_line_id in available_lines:
                continue
            if available_lines:
                payment.payment_method_line_id = available_lines[0]
            else:
                payment.payment_method_line_id = False

    def _get_internal_transfer_payment_method_line(self, journal, payment_type):
        method_lines = journal._get_available_payment_method_lines(payment_type)
        if not method_lines:
            raise UserError(_(
                "No %(payment_type)s payment method is configured on journal %(journal)s. "
                "Configure Outstanding Payments/Receipts on the journal payment methods.",
                payment_type=dict(self._fields['payment_type'].selection).get(payment_type, payment_type),
                journal=journal.display_name,
            ))
        manual_line = method_lines.filtered(lambda line: line.code == 'manual')[:1]
        return manual_line or method_lines[0]

    @api.depends(
        'journal_id',
        'partner_id',
        'partner_type',
        'is_internal_transfer',
        'destination_journal_id',
        'company_id',
    )
    def _compute_destination_account_id(self):
        transfers = self.filtered('is_internal_transfer')
        others = self - transfers
        for payment in transfers:
            payment.destination_account_id = payment.company_id.transfer_account_id
        if others:
            super(AccountPayment, others)._compute_destination_account_id()

    @api.depends('partner_id', 'company_id', 'payment_type', 'destination_journal_id', 'is_internal_transfer')
    def _compute_available_partner_bank_ids(self):
        super()._compute_available_partner_bank_ids()
        for payment in self.filtered(lambda p: p.is_internal_transfer and p.destination_journal_id):
            payment.available_partner_bank_ids = payment.destination_journal_id.bank_account_id

    def _get_aml_default_display_name_list(self):
        self.ensure_one()
        if self.is_internal_transfer:
            if self.payment_type == 'inbound':
                label = _('Transfer to %s', self.journal_id.display_name)
            else:
                label = _('Transfer from %s', self.journal_id.display_name)
            if self.memo:
                return [
                    ('label', label),
                    ('sep', ': '),
                    ('memo', self.memo),
                ]
            return [('label', label)]
        return super()._get_aml_default_display_name_list()

    @api.model
    def _get_trigger_fields_to_synchronize(self):
        return super()._get_trigger_fields_to_synchronize() + (
            'is_internal_transfer',
            'destination_journal_id',
        )

    def action_post(self):
        for payment in self.filtered(lambda p: not p.payment_method_line_id):
            method_line = payment._get_internal_transfer_payment_method_line(
                payment.journal_id,
                payment.payment_type,
            )
            payment.write({'payment_method_line_id': method_line.id})

        transfers = self.filtered(
            lambda p: p.is_internal_transfer
            and p.destination_journal_id
            and not p.paired_internal_transfer_payment_id
        )
        for payment in transfers:
            if payment.amount <= 0:
                raise UserError(_("Internal transfer amount must be greater than zero."))
            if payment.payment_type != 'outbound':
                raise UserError(_(
                    "Internal transfers must be confirmed as Send payments. "
                    "The matching Receive payment is created automatically on %(journal)s.",
                    journal=payment.destination_journal_id.display_name,
                ))

        res = super().action_post()

        transfers._create_paired_internal_transfer_payment()
        return res

    def _prepare_paired_internal_transfer_vals(self):
        self.ensure_one()
        payment_type = 'inbound' if self.payment_type == 'outbound' else 'outbound'
        journal = self.destination_journal_id
        method_line = self._get_internal_transfer_payment_method_line(journal, payment_type)
        return {
            'is_internal_transfer': True,
            'payment_type': payment_type,
            'partner_type': self.partner_type,
            'partner_id': self.partner_id.id,
            'amount': self.amount,
            'date': self.date,
            'memo': self.memo,
            'journal_id': journal.id,
            'destination_journal_id': self.journal_id.id,
            'payment_method_line_id': method_line.id,
            'currency_id': self.currency_id.id,
            'paired_internal_transfer_payment_id': self.id,
        }

    def _create_paired_internal_transfer_payment(self):
        for payment in self:
            transfer_account = payment.company_id.transfer_account_id
            if not transfer_account:
                raise UserError(_(
                    "Configure an Internal Transfer account under "
                    "Accounting -> Configuration -> Settings."
                ))

            paired_payment = self.env['account.payment'].create(
                payment._prepare_paired_internal_transfer_vals(),
            )
            paired_payment.action_post()
            payment.paired_internal_transfer_payment_id = paired_payment

            payment.message_post(
                body=_(
                    "A paired internal transfer payment was created: %(link)s",
                    link=paired_payment._get_html_link(),
                ),
            )
            paired_payment.message_post(
                body=_(
                    "This payment was created from: %(link)s",
                    link=payment._get_html_link(),
                ),
            )

            if payment.move_id and paired_payment.move_id:
                lines = (payment.move_id.line_ids + paired_payment.move_id.line_ids).filtered(
                    lambda line: line.account_id == transfer_account and not line.reconciled
                )
                if len(lines) >= 2:
                    lines.reconcile()

    def action_open_paired_payment(self):
        self.ensure_one()
        if not self.paired_internal_transfer_payment_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Paired Internal Transfer'),
            'res_model': 'account.payment',
            'view_mode': 'form',
            'res_id': self.paired_internal_transfer_payment_id.id,
        }

    def action_open_destination_journal(self):
        self.ensure_one()
        if not self.destination_journal_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Destination Journal'),
            'res_model': 'account.journal',
            'view_mode': 'form',
            'target': 'new',
            'res_id': self.destination_journal_id.id,
        }
