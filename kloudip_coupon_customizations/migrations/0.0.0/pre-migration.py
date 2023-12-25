# -*- coding: utf-8 -*-
def migrate(cr, version):
   cr.execute("UPDATE sale_order SET next_invoice_date='2023-03-27' WHERE next_invoice_date < start_date")
   cr.execute("CREATE TABLE coupon_loyalty_temp (sale_id INT, coupon_id INT, coupon_code VARCHAR (255), c_state VARCHAR(255))")
   cr.execute("INSERT INTO coupon_loyalty_temp (sale_id, coupon_id, coupon_code, c_state) SELECT 'sale_order_id', 'id', 'code', 'state' FROM coupon_coupon WHERE sale_order_id IS NOT NULL")
