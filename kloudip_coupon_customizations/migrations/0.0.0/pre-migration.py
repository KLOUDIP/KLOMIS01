# -*- coding: utf-8 -*-
def migrate(cr, version):
   cr.execute("UPDATE sale_order SET next_invoice_date='2023-03-27' WHERE next_invoice_date < start_date")