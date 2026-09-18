# -*- coding: utf-8 -*-
import logging

from odoo import models, _

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _fios_partners_to_sync(self):
        """Active FIOS accounts affected by these customer invoices.

        An invoice is usually addressed to an invoice-type child contact
        ("Company, Person - I"), while the FIOS account sits on another record
        of the same customer, so the match is done on the commercial partner.
        """
        SaleOrder = self.env['sale.order'].sudo()
        invoices = self.sudo().filtered(lambda m: m.move_type == 'out_invoice')
        if SaleOrder._fios_invoice_scope_is_fios_only():
            invoices = invoices.filtered(lambda m: any(
                line.product_id.product_tmpl_id.fios_service
                or line.product_id.product_tmpl_id.fios_tier_id
                for line in m.invoice_line_ids))
        commercials = invoices.commercial_partner_id
        if not commercials:
            return self.env['res.partner']
        return self.env['res.partner'].sudo().search([
            ('id', 'child_of', commercials.ids),
            ('fios_provision_state', '=', 'active'),
            ('fios_account_item_id', '!=', False),
        ])

    def _fios_sync_days_left(self, description, note_unchanged=True):
        """Re-sync the FIOS days-left counter of every FIOS account behind these
        customer invoices. Never raises: an accounting action must not fail or
        roll back because FIOS is unreachable."""
        try:
            partners = self._fios_partners_to_sync()
        except Exception:
            _logger.exception("FIOS: could not resolve FIOS accounts for invoices %s", self.ids)
            return
        if not partners:
            return

        SaleOrder = self.env['sale.order'].sudo()
        for partner in partners:
            try:
                # Savepoint: a failure here must never roll back the accounting.
                with self.env.cr.savepoint():
                    result = SaleOrder._fios_push_days_left(partner, description=description[:250])
            except Exception as e:
                _logger.exception("FIOS: days-left sync failed for partner %s", partner.id)
                result = {'ok': False, 'error': str(e), 'days': None}
            if note_unchanged or not result.get('ok') or result.get('changed'):
                self._fios_post_days_left_note(partner, result)

    def _fios_move_names(self):
        return ', '.join(n for n in self.mapped('name') if n and n != '/')

    def _invoice_paid_hook(self):
        """When a customer invoice is paid, move the FIOS "days left" counter to
        the next invoice falling due (or the paid subscription period)."""
        res = super()._invoice_paid_hook()
        names = self._fios_move_names()
        self._fios_sync_days_left(_("Invoice paid: %s") % names if names else _("Invoice paid"))
        return res

    def _post(self, soft=True):
        """A newly posted customer invoice can be the earliest one falling due
        (e.g. a hardware invoice with a short term, or the subscription invoice
        for the next period), so days left is re-synced straight away."""
        posted = super()._post(soft=soft)
        invoices = posted.filtered(lambda m: m.move_type == 'out_invoice' and m.state == 'posted')
        if invoices:
            names = invoices._fios_move_names()
            # Zero-amount invoices already went through _invoice_paid_hook inside
            # super(); only note the sync here when it actually changed something.
            invoices._fios_sync_days_left(
                _("Invoice posted: %s") % names if names else _("Invoice posted"),
                note_unchanged=False)
        return posted

    def button_draft(self):
        """Reset to draft / cancel (button_cancel goes through here): the
        invoice no longer counts as owed, so the counter moves on."""
        was_posted = self.filtered(lambda m: m.move_type == 'out_invoice' and m.state == 'posted')
        res = super().button_draft()
        if was_posted:
            names = was_posted._fios_move_names()
            was_posted._fios_sync_days_left(
                _("Invoice reset to draft: %s") % names if names else _("Invoice reset to draft"),
                note_unchanged=False)
        return res

    def _fios_post_days_left_note(self, partner, result):
        if result.get('ok') and result.get('days') is None:
            return  # nothing to compute from (no open invoice, no subscription)
        if result.get('ok'):
            body = _("FIOS days left for %(partner)s set to %(days)s "
                     "(runs to %(due)s - %(source)s).") % {
                'partner': partner.display_name, 'days': result['days'],
                'due': result['due_date'], 'source': result['source']}
        else:
            body = _("FIOS days left for %(partner)s could not be updated: %(error)s. "
                     "Use Provision / Resume on the contact to re-sync.") % {
                'partner': partner.display_name, 'error': result.get('error')}
        for move in self.sudo().filtered(
                lambda m: m.move_type == 'out_invoice'
                and m.commercial_partner_id == partner.commercial_partner_id):
            try:
                with self.env.cr.savepoint():
                    move.message_post(body=body)
            except Exception:
                _logger.exception("FIOS: could not post days-left note on move %s", move.id)


class AccountPartialReconcile(models.Model):
    _inherit = 'account.partial.reconcile'

    def unlink(self):
        """Removing a payment from an invoice makes it owed again: re-sync the
        FIOS days left of the customers concerned."""
        invoices = (self.debit_move_id.move_id | self.credit_move_id.move_id).filtered(
            lambda m: m.move_type == 'out_invoice' and m.state == 'posted')
        res = super().unlink()
        invoices = invoices.exists()
        if invoices:
            names = invoices._fios_move_names()
            invoices._fios_sync_days_left(
                _("Payment removed from: %s") % names if names else _("Payment removed"),
                note_unchanged=False)
        return res
