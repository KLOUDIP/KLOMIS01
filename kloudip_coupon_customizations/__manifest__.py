# -*- encoding: utf-8 -*-

{
    'name': 'KLOUDIP Coupon Customizations',
    'summary': "Coupon Customizations for KLOUDIP",
    'description': """
Setting coupon again to valid state, when sale order returned
    """,
    'version': '1.1.3',
    'category': 'Sale',
    'author': 'Nisus Solutions (Pvt) Ltd',
    'website': 'http://www.nisus.lk',
    'depends': [
        'account',
        'sale_coupon',
        'sale_coupon_taxcloud',
        'coupon',
        'stock',
        'sale_management',
        'product',
        'mail',
    ],
    'data': [
        'security/coupon_security.xml',
        'data/mail_data.xml',
        'data/coupon_email_data.xml',
        'views/product_template_views.xml',
        'views/coupon_coupon_views.xml',
        'views/coupon_program_views.xml',
        'views/sale_order_views.xml',
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
        'wizards/sale_coupon_apply_code_views.xml',
        'wizards/sale_make_invoice_advance_views.xml',
        'reports/coupon_report_templates.xml'
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
# actual version 1.1.6
