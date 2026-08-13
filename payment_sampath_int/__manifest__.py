# -*- coding: utf-8 -*-

{
    'name': 'Payment Provider: Sampath Bank International',
    'version': '1.0.0',
    "author": "Ranga Dharmapriya",
    "email": "rangadharmapriya@gmail.com",
    'category': 'Accounting/Payment Providers',
    "website": "",
    "support": "rangadharmapriya@gmail.com",
    'sequence': 350,
    'summary': "A Sri Lankan payment provider for USD payments powered by Sampath Bank",
    "description": """
        A Sri Lankan payment provider for USD payments powered by Sampath Bank
    """,
    'depends': [
        'payment'
    ],
    'data': [
        'views/payment_provider_views.xml',
        'views/payment_sampath_templates.xml',
        'data/payment_provider_data.xml',
    ],
    'application': False,
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'license': 'LGPL-3',
}
