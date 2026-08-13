# -*- coding: utf-8 -*-
###############################################################################
#
#    Fortutech IMS Pvt. Ltd.
#    Copyright (C) 2016-TODAY Fortutech IMS Pvt. Ltd.(<http://www.fortutechims.com>).
#
###############################################################################
from collections import defaultdict
import logging
from datetime import datetime
from odoo import api, exceptions, fields, models, _
# from odoo.tools import consteq, float_round, image_resize_images, image_resize_image, ustr
from odoo.exceptions import ValidationError, UserError
from odoo import api, SUPERUSER_ID
from odoo.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.misc import formatLang
_logger = logging.getLogger(__name__)

class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'
    
    def _reconcile_after_transaction_done(self):
        sales_orders = self.mapped('sale_order_ids').filtered(lambda so: so.state in ('draft', 'sent'))
        res_confirm_order = self.env['ir.config_parameter'].sudo().get_param('fims_sale_automatic_workflow.web_order_conf')
        if not res_confirm_order:
            raise UserError(_("Please configure website order processing."))
        
        if res_confirm_order == 'conf_quo':
            for so in sales_orders:
                so.with_context(send_email=True).action_confirm()
        
            invoices = self.mapped('invoice_ids').filtered(lambda inv: inv.state == 'draft')
            if invoices:
                invoices.action_invoice_open()
                # Create & Post the payments.
            payments = defaultdict(lambda: self.env['account.payment'])
            for trans in self:
                if trans.payment_id:
                    payments[trans.acquirer_id.company_id.id] += trans.payment_id
                    continue
    
                payment_vals = trans._prepare_account_payment_vals()
                payment = self.env['account.payment'].create(payment_vals)
                payments[trans.acquirer_id.company_id.id] += payment
    
                # Track the payment to make a one2one.
                trans.payment_id = payment
    
            for company in payments:
                payments[company].with_context(force_company=company, company_id=company).post()
            
        if res_confirm_order == 'conf_quo_and_inv':
            for so in sales_orders:
                so.with_context(send_email=True).action_confirm()
        
            ctx_company = {'company_id': self.acquirer_id.company_id.id,
                           'force_company': self.acquirer_id.company_id.id}
            for trans in self.filtered(lambda t: t.sale_order_ids):
                trans = trans.with_context(ctx_company)
                trans.sale_order_ids._force_lines_to_invoice_policy_order()
                invoices = trans.sale_order_ids._create_invoices()
                trans.invoice_ids = [(6, 0, invoices.ids)]
            
            payments = defaultdict(lambda: self.env['account.payment'])
            for trans in self:
                if trans.payment_id:
                    payments[trans.acquirer_id.company_id.id] += trans.payment_id
                    continue
    
                payment_vals = trans._prepare_account_payment_vals()
                payment = self.env['account.payment'].create(payment_vals)
                payments[trans.acquirer_id.company_id.id] += payment
                # Track the payment to make a one2one.
                trans.payment_id = payment
    
        if res_confirm_order == 'conf_quo_and_validate_inv':
            for so in sales_orders:
                so.with_context(send_email=True).action_confirm()
        
            ctx_company = {'company_id': self.acquirer_id.company_id.id,
                           'force_company': self.acquirer_id.company_id.id}
            for trans in self.filtered(lambda t: t.sale_order_ids):
                trans = trans.with_context(ctx_company)
                trans.sale_order_ids._force_lines_to_invoice_policy_order()
                invoices = trans.sale_order_ids._create_invoices()
                trans.invoice_ids = [(6, 0, invoices.ids)]
            
            payments = defaultdict(lambda: self.env['account.payment'])
            for trans in self:
                if trans.payment_id:
                    payments[trans.acquirer_id.company_id.id] += trans.payment_id
                    continue
    
                payment_vals = trans._prepare_account_payment_vals()
                payment = self.env['account.payment'].create(payment_vals)
                payments[trans.acquirer_id.company_id.id] += payment
    
                trans.payment_id = payment
    
            invoices = self.mapped('invoice_ids').filtered(lambda inv: inv.state == 'draft')
            if invoices:
                invoices.post()
        
        if res_confirm_order == 'conf_quo_inv_payment':
            sales_orders = self.mapped('sale_order_ids').filtered(lambda so: so.state in ('draft', 'sent'))
            for so in sales_orders:
                # For loop because some override of action_confirm are ensure_one.
                so.action_confirm()
            # send order confirmation mail
            sales_orders._send_order_confirmation_mail()
            # invoice the sale orders if needed
            self._invoice_sale_orders()
            invoices = self.mapped('invoice_ids').filtered(lambda inv: inv.state == 'draft')
            invoices.post()
    
            # Create & Post the payments.
            payments = defaultdict(lambda: self.env['account.payment'])
            for trans in self:
                if trans.payment_id:
                    payments[trans.acquirer_id.company_id.id] += trans.payment_id
                    continue
    
                payment_vals = trans._prepare_account_payment_vals()
                payment = self.env['account.payment'].create(payment_vals)
                payments[trans.acquirer_id.company_id.id] += payment
    
                # Track the payment to make a one2one.
                trans.payment_id = payment
    
            for company in payments:
                payments[company].with_context(force_company=company, company_id=company).post()
            
            default_template = self.env['ir.config_parameter'].sudo().get_param('sale.default_email_template')
            if default_template:
                for trans in self.filtered(lambda t: t.sale_order_ids):
                    ctx_company = {'company_id': trans.acquirer_id.company_id.id,
                                   'force_company': trans.acquirer_id.company_id.id,
                                   'mark_invoice_as_sent': True,
                                   }
                    trans = trans.with_context(ctx_company)
                    for invoice in trans.invoice_ids:
                        
                        try:
                            invoice.message_post_with_template(int(default_template), email_layout_xmlid="mail.mail_notification_paynow")
                        except:
                            pass
#
    def _invoice_sale_orders(self):
        ctx_company = {'company_id': self.acquirer_id.company_id.id,
                       'force_company': self.acquirer_id.company_id.id}
        for trans in self.filtered(lambda t: t.sale_order_ids):
            trans = trans.with_context(ctx_company)
            trans.sale_order_ids._force_lines_to_invoice_policy_order()
            invoices = trans.sale_order_ids._create_invoices()
            trans.invoice_ids = [(6, 0, invoices.ids)]