# -*- coding: utf-8 -*-
{
    'name': 'Contact Image',
    "summary": "This module allow add image field to res partner contact address form",
    "description": "This module allow add image field to res partner contact address form",
    'category': 'Contact',
    'version': '15.0.1.0.1',
    "author": "BitbrainHub",
    "email": "bitbrainhub@gmail.com",
    'depends': [
        'base',
        'contacts'
    ],
    'data': [
        'views/res_partner_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'licence': 'LGPL-3',
}
