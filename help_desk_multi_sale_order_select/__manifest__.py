# -*- coding: utf-8 -*-
{
    'name': 'HelpDesk Multi Sale Order Select',
    'description': 'This module is for Multi Sale Order Select',
    'category': 'Helpdesk',
    'summary': 'Multi Sale Order Select',
    'version': '19.0.3.0.0',
    'author': "VK Data ApS",
    'website': "https://vkdata.dk",
    'data': [
        'views/helpdesk_ticket_views.xml',
        'views/sale_order_views.xml',
    ],
    'depends': ['helpdesk', 'helpdesk_sale', 'sale_management', 'sale_timesheet'],
    'license': 'OPL-1',
    'application': False,
    'installable': True,
    'auto_install': False,
}
