# -*- encoding: utf-8 -*-

{
    'name': 'KLOUDIP SO Coordinator And Billing Responsible',
    'summary': "Coordinator and billing responsible for portal view",
    'description': """
            Add coordinator and billing responsible to portal view
    """,
    'version': '16.0.2.0.0',
    'category': 'Sale',
    'author': 'Nisus Solutions (Pvt) Ltd',
    'website': 'http://www.nisus.lk',
    'depends': [
        'kloudip_so_coordinator_and_billing_responsible',
        'portal'
    ],
    'data': [
        'views/portal_templates.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
# Actual Version 1.0.6

