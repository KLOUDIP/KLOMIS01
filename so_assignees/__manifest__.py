# -*- coding: utf-8 -*-
{
    'name': 'SO Assignees',
    'version': '1.0.1',
    'summary': 'Assign coordinator to the SO',
    'description': """
================
This module allow to assign coordinator to a SO and it will calculate unit counts by coordinators.
""",
    'category': 'Tools',
    "author": "BitbrainHub",
    "email": "bitbrainhub@gmail.com",
    'depends': ['sale', 'helpdesk', 'hr', 'fios_connector'],
    'data': [
        'security/ir.model.access.csv',
        'views/sale_order_views.xml',
        'views/hr_employee_views.xml'
    ],
    'licence': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False,

}
