# -*- encoding: utf-8 -*-

{
    'name': 'KLOUDIP Coupon Customizations',
    'summary': "Coupon Customizations for KLOUDIP",
    'description': """
Setting coupon again to valid state, when sale order returned
    """,
    'version': '15.0.2.0.11',
    'category': 'Sale',
    'author': 'Nisus Solutions (Pvt) Ltd',
    'website': 'http://www.nisus.lk',
    'depends': [
        'account',
        'loyalty',
        'sale_loyalty',
        'stock',
        'sale_management',
        'product',
        'mail',
        'sale_subscription'
    ],
    'data': [
        'security/coupon_security.xml',
        'security/ir.model.access.csv',
        'data/mail_data.xml',
        'data/coupon_email_data.xml',
        'views/product_template_views.xml',
        'views/loyalty_card_views.xml',
        'views/loyalty_program_views.xml',
        'views/sale_order_views.xml',
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
        'wizards/sale_loyalty_coupon_wizard_views.xml',
        'wizards/sale_make_invoice_advance_views.xml',
        'wizards/subscription_make_invoice_advance_views.xml',
        'reports/coupon_report_templates.xml'
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
