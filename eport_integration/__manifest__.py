# -*- coding: utf-8 -*-
{
    'name': 'EPORT Integration',
    "summary": "This module allow integrate the Odoo with EPORT",
    "description": "This module allow integrate the Odoo with EPORT",
    'category': 'Contact',
    'version': '19.0.2.0.0',
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
    'license': 'OPL-1',
    'application': False,
    'installable': True,
    'auto_install': False,
}
