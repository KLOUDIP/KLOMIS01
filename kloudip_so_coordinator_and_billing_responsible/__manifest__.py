# -*- encoding: utf-8 -*-

{
    'name': 'KLOUDIP SO Coordinator And Billing Responsible',
    'summary': "Coordinator and billing responsible for sales order",
    'description': """
Add coordinator and billing responsible to sales order
    """,
    'version': '1.0.2',
    'category': 'Sale',
    'author': 'Nisus Solutions (Pvt) Ltd',
    'website': 'http://www.nisus.lk',
    'depends': [
        'sale_management',
        'account',
        'hr',
    ],
    'data': [
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
# Actual Version 1.0.5

