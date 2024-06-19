# -*- coding: utf-8 -*-

{
    "name": "Subscription Packages",
    "author": "Ranga Dharmapriya",
    "email": "rangadharmapriya@gmail.com",
    "website": "",
    "support": "",
    "category": "Subscription",
    "summary": "Add subscription package option to the website invoice preview",
    "description": """
Add subscription package option to the website invoice preview
""",
    "version": "17.0.1.2.2",
    "depends": [
        'sale',
        'sale_subscription',
        'account_accountant',
        'sale_management',
        'sale_pdf_quote_builder'
    ],
    "data": [
        'security/ir.model.access.csv',
        'views/sale_order_views.xml',
        'views/sale_portal_templates.xml',
        'views/sale_order_template_views.xml',
        'report/sale_order_templates.xml'
    ],
    'assets': {
        'web.assets_frontend': [
            'subscription_packages/static/src/scss/sale_portal.scss',
            'subscription_packages/static/src/js/sale_portal.js',
            ]
    },
    "application": False,
    "auto_install": False,
    "installable": True,
    "license": 'LGPL-3'
}
