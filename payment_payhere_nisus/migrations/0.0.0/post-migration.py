# -*- coding: utf-8 -*-
def migrate(cr, version):
   """
        Creating a temporary field to store the percentage data
   """
   cr.execute('DELETE FROM payment_transaction WHERE partner_id is null;')
