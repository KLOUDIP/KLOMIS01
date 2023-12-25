{
    'name': 'Payment Provider: Sampath Bank',
    'version': '2.0.1',
    'category': 'Accounting/Payment Providers',
    'summary': 'An payment provider',
    'description': '''''',
    'author': 'VK DATA ApS',
    'website': 'https://www.vkdata.dk/',
    'depends': ['payment', 'website_sale'],
    'data' : [
        'views/payment_provider_views.xml',
        'views/payment_transaction_views.xml',
        'views/payment_templates.xml',
        'data/payment_provider_data.xml',
    ],
    'demo': [

    ],
    'qweb' : [

    ],
    'assets': {
        'web.assets_frontend': [
            'vkd_payment_sampath_bank/static/src/js/payment_form.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'external_dependencies': {
        # "python": [
        #     'plotly', # Just to show how to write the dependency
        # ],
    },
    "license": "OPL-1",
}
