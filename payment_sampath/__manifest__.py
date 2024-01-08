# -*- coding: utf-8 -*-

{
    'name': 'Payment Provider: Sampath Bank',
    'version': '1.0.0',
    "author": "Ranga Dharmapriya",
    "email": "rangadharmapriya@gmail.com",
    'category': 'Accounting/Payment Providers',
    "website": "",
    "support": "rangadharmapriya@gmail.com",
    'sequence': 350,
    'summary': "A Sri Lankan payment provider powered by Sampath Bank",
    "description": """
A Sri Lankan payment provider powered by Sampath Bank
""",
    'depends': [
        'payment'
    ],
    'data': [
        'views/payment_provider_views.xml',
        'data/payment_provider_data.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'https://sampath.paycorp.lk/webinterface/qw/paycorp_payments.js',
            'payment_sampath/static/src/js/sampath_options.js',
            'payment_sampath/static/src/js/payment_form.js',
        ],
    },
    'application': False,
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'license': 'LGPL-3',
}
