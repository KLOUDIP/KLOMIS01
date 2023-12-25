# -*- coding: utf-8 -*-
def migrate(cr, version):
    cr.execute("UPDATE loyalty_card b SET b.sale_order_id = a.sale_id, b.state = a.c_state FROM coupon_loyalty_temp a WHERE a.coupon_code = b.code")
    cr.execute("DROP TABLE IF EXISTS coupon_loyalty_temp")
