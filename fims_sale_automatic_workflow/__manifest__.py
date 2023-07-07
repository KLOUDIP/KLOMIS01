# -*- coding: utf-8 -*-
###############################################################################
#
#    Fortutech IMS Pvt. Ltd.
#    Copyright (C) 2016-TODAY Fortutech IMS Pvt. Ltd.(<http://www.fortutechims.com>).
#
###############################################################################
{
    'name': 'Website Sale Automatic Workflow',
    'category': 'Website Sale',
    'summary': 'Manage automatic sale order confirmation, invoice creation, invoice validate, and pay invoice.',
    'version': '1.0.0',
    'license': 'OPL-1',
    'description': """Manage automatic sale order confirmation, invoice creation, invoice validate, and pay invoice.""",
    'depends': ['sale_management', 'website_sale'],
    'author': 'Fortutech IMS Pvt. Ltd.',
    'website': 'https://www.fortutechims.com',
    'data': [
        'data/res_config_settings_data.xml',
        'views/res_config_settings_views.xml',
        'views/website_templates.xml',
    ],
    "price": 39,
    "currency": "EUR",
    "images": ['static/description/banner.png'],
    "installable": True,
    "application": True,
    "auto_install": False,
}