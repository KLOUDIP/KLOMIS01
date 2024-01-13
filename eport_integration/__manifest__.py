# -*- coding: utf-8 -*-
{
    'name': 'EPORT Integration',
    "summary": "This module allow integrate the Odoo with EPORT",
    "description": "This module allow integrate the Odoo with EPORT",
    'category': 'Contact',
    'version': '16.0.1.0.3',
    "author": "BitbrainHub",
    "email": "bitbrainhub@gmail.com",
    'depends': [
        'base',
        'contacts',
        'product',
        'sale'
    ],
    'data': [
        "data/eport_data.xml",
        "data/ir_cron_data.xml",
        "security/ir.model.access.csv",
        'views/res_partner_views.xml',
        'views/product_product_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'licence': 'LGPL-3',
}
