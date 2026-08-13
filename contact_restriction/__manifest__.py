# -*- coding: utf-8 -*-
{
    'name': 'Contact Restriction',
    "summary": "This module allow block/unblock contacts",
    "description": "This module allow block/unblock contacts",
    'category': 'Contact',
    'version': '19.0.2.0.0',
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
    'license': 'OPL-1',
    'application': False,
    'installable': True,
    'auto_install': False,
}
