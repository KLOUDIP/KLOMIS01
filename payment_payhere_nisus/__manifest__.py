# -*- coding: utf-8 -*-
{
    'name': 'Payhere Payment Acquirer',
    'category': 'Payment Gateway',
    'summary': 'Payment Acquirer: Payhere Implementation',
    'version': '1.0.7',
    'website': 'http://www.nisus.lk',
    'author': 'Nisus Solutions (Pvt) Ltd',
    'description': """Payhere (ePay) Acquirer""",
    'depends': ['payment'],
    'data': [
        'views/payment_payhere_templates.xml',
        'views/payment_provider_views.xml',
        'data/payment_provider_data.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'license': 'LGPL-3',
}


