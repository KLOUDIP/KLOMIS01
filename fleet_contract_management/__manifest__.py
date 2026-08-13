# -*- coding: utf-8 -*-
{
    'name': 'Fleet Contract Management',
    "summary": "This module allow to add billing contact to contract view",
    "description": "This module allow to add billing contact to contract view",
    'category': 'fleet',
    'version': '2.0.0',
    "author": "Nisus Solutions (Pvt) Ltd",
    "website": "https://nisus.lk/",
    'data': [
        'views/fleet_vehicle_cost_views.xml',
        'views/res_partner_views.xml',
    ],
    'depends': [
        'fleet',
        'sale_subscription',
        'account',
        'sale'
    ],
    'license': 'LGPL-3',
}
