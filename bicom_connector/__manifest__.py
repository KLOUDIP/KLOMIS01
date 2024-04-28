# -*- coding: utf-8 -*-
{
    "name": "BiCom Connector",
    "author": "Ranga Dharmapriya",
    "email": "rangadharmapriya@gmail.com",
    "website": "",
    "support": "",
    "category": "MISC",
    "summary": "BiCom Integration with Odoo",
    "description": """
        This module allow to integrate BiCom with Odoo CRM
    """,
    "version": "17.0.1.0.3",
    "depends": [
        'base',
        'voip'
    ],
    "data": [
        'data/ir_cron_data.xml',
        'views/res_users_views.xml'
    ],
    'assets': {},
    "application": False,
    "auto_install": False,
    "installable": True,
    "license": 'LGPL-3'
}
