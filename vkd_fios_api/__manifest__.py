# -*- coding: utf-8 -*-
{
    'name': "Trazet FIOS API",
    'summary': "Provision and manage FIOS (Wialon) customer accounts from Odoo",
    'description': """
        Standalone integration with the FIOS platform (fios-api.kloudip.com, Wialon ajax.html).

        Provides:
        - FIOS session lifecycle (token login -> SID, keep-alive, re-login)
        - Customer account provisioning: create user -> resource -> account
        - Post-provisioning operations: billing services/limits, payment, enable/disable
        - Retry/ops log with exponential backoff
    """,
    'author': 'VK DATA ApS',
    'website': 'https://vkdata.dk/',
    'category': 'Hidden',
    'version': '19.0.2.3.0',
    # Pending release: 19.0.2.7.0 - FIOS Administrator / FIOS User groups,
    # menu and contact-tab gating, and the printable device list report.
    # Bump 'version' above to that value when this goes out.
    'license': 'OPL-1',
    # field_service_extension is depended on only for its group_fsm_tech_team
    # record, which still gates the device IMEI / phone columns. The FIOS
    # Administrator / FIOS User roles themselves live in security/fios_security.xml.
    'depends': ['base', 'sale', 'sale_subscription', 'product',
                'field_service_extension'],
    'data': [
        'security/fios_security.xml',
        'security/ir.model.access.csv',
        'data/fios_service_tier_data.xml',
        'data/ir_config_parameter.xml',
        'data/ir_cron_data.xml',
        'views/fios_service_tier_views.xml',
        'views/fios_api_log_views.xml',
        'views/res_partner_views.xml',
        'views/res_users_views.xml',
        'views/product_template_views.xml',
        'views/sale_subscription_plan_views.xml',
        'views/menus.xml',
        'reports/fios_device_report.xml',
        'wizard/fios_account_import_views.xml',
    ],
    'external_dependencies': {
        'python': ['requests', 'cryptography'],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}