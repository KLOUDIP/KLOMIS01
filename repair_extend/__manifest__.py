# -*- coding: utf-8 -*-
{
    'name': 'Repair Extend',
    "summary": "This module allow add new feature to repair module",
    "description": "This module allow add new feature to repair module",
    'category': 'Inventory/Inventory',
    'version': '1.0.3',
    "author": "BitbrainHub",
    "email": "bitbrainhub@gmail.com",
    'depends': [
        'repair',
        'helpdesk_repair'
    ],
    'data': [
        'views/sale_order_views.xml',
        'views/repair_views.xml',
        'views/stock_picking_views.xml'
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'licence': 'LGPL-3',
}
