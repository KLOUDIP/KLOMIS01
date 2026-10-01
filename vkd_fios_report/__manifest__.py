# -*- coding: utf-8 -*-
{
    'name': "FIOS Account Report",
    'summary': "Billing report of synced FIOS accounts: status, days left, units and grace period",
    'description': """
        Reporting on top of vkd_fios_api (Contacts > FIOS Reporting):

        - FIOS Accounts: one line per synced FIOS contact with account status
          (Active / Blocked), days left and estimated block date, active /
          inactive unit counts and 7-day grace period status (In Use / Not In Use).
          Contacts whose FIOS status has never been read are left out.
        - FIOS Units: every device of those contacts, grouped by contact, with
          Activated / Inactive filters and a pivot view.
        - A nightly scheduled action that re-reads status and devices from FIOS
          for every active account, so the report does not depend on someone
          clicking Refresh on each contact.
    """,
    'author': 'VK DATA ApS',
    'website': 'https://vkdata.dk/',
    'category': 'Hidden',
    'version': '19.0.1.0.0',
    'license': 'OPL-1',
    'depends': ['contacts', 'vkd_fios_api'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/fios_account_report_views.xml',
        'views/fios_unit_report_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
