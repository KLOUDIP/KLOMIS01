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

    def _invoice_paid_hook(self):
        """When a customer invoice is paid, move the FIOS "days left" counter to
        the days remaining until the customer's next due invoice."""
        res = super()._invoice_paid_hook()
        try:
            partners = self._fios_partners_to_sync()
        except Exception:
            _logger.exception("FIOS: could not resolve FIOS accounts for paid invoices %s",
                              self.ids)
            return res
        if not partners:
            return res

        SaleOrder = self.env['sale.order'].sudo()
        names = ', '.join(n for n in self.mapped('name') if n and n != '/')
        description = _("Invoice paid: %s") % names if names else _("Invoice paid")
        for partner in partners:
            try:
                # Savepoint: a failure here must never roll back the payment.
                with self.env.cr.savepoint():
                    result = SaleOrder._fios_push_days_left(partner, description=description[:250])
            except Exception as e:
                _logger.exception("FIOS: days-left sync after payment failed for partner %s",
                                  partner.id)
                result = {'ok': False, 'error': str(e), 'days': None}
            self._fios_post_days_left_note(partner, result)
        return res

    def _fios_post_days_left_note(self, partner, result):
        if result.get('ok') and result.get('days') is None:
            return  # nothing to compute from (no open invoice, no subscription)
        if result.get('ok'):
            body = _("FIOS days left for %(partner)s set to %(days)s "
                     "(next due %(due)s - %(source)s).") % {
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
