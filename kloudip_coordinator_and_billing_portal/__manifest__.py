# -*- encoding: utf-8 -*-
{
    'name': 'KLOUDIP SO Coordinator And Billing Responsible',
    'summary': "Coordinator and billing responsible for portal view",
    'description': """
            Add coordinator and billing responsible to portal view
    """,
    'version': '19.0.1.0.0',
    'category': 'Sale',
    'author': "VK DATA ApS",
    'website': "https://vkdata.dk",
    'depends': [
        'kloudip_so_coordinator_and_billing_responsible',
        'portal'
    ],
    'data': [
        'views/portal_templates.xml',
    ],
    'license': 'OPL-1',
    'installable': True,
    'application': False,
    'auto_install': False,
}
