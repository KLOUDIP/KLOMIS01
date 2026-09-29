# -*- coding: utf-8 -*-
import logging

from odoo import models

_logger = logging.getLogger(__name__)

# Online payments through these providers only confirm the quotation.
# The invoice is created later by the accounting team, in the journal they choose.
NO_INVOICE_PROVIDER_CODES = ('sampath',)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _invoice_sale_orders(self):
        """ Do not invoice sales orders paid online through Sampath.

        After a successful online payment Odoo confirms the order and, through
        `sale.automatic_invoice` or the subscription engine (sale_subscription
        forces the first-period invoice for subscriptions), also creates and
        posts an invoice. This module loads after sale_subscription, so skipping
        the super() call here skips every layer of that invoicing.

        Order confirmation and the account.payment are untouched: the payment
        stays as an outstanding credit on the customer and is applied when the
        invoice is created manually.
        """
        skipped = self.filtered(
            lambda tx: tx.provider_code in NO_INVOICE_PROVIDER_CODES and tx.sale_order_ids
        )
        for tx in skipped:
            _logger.info(
                "Online payment %s (%s): order(s) %s confirmed, automatic invoicing skipped.",
                tx.reference, tx.provider_code, ", ".join(tx.sale_order_ids.mapped('name')),
            )
        others = self - skipped
        if others:
            return super(PaymentTransaction, others)._invoice_sale_orders()
        return None
