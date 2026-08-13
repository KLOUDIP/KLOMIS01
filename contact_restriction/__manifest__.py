# -*- coding: utf-8 -*-
{
    'name': 'Contact Restriction',
    "summary": "This module allow block/unblock contacts",
    "description": "This module allow block/unblock contacts",
    'category': 'Contact',
    'version': '1.0.2',
    "author": "BitbrainHub",
    "email": "bitbrainhub@gmail.com",
    'depends': [
        'contacts',
        'sale',
        'account'
    ],
    'data': [
        'views/res_partner_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'licence': 'LGPL-3',
}