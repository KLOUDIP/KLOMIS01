# -*- coding: utf-8 -*-
# KLOMIS01 v17 -> v19 REMOVAL SHELL - load-only, uninstall after go-live.
{
    'name': 'Payment Provider: Sampath Bank International',
    'version': '19.0.1.0.0',
    'author': "Ranga Dharmapriya",
    'category': 'Accounting/Payment Providers',
    'sequence': 350,
    'summary': "[REMOVAL SHELL] Sampath Bank USD provider - scheduled for uninstall",
    'description': """
        Load-only shell retained for the 17.0 -> 19.0 upgrade.

        payment_sampath_templates.xml and payment_provider_data.xml are kept
        deliberately: payment.provider.redirect_form_view_id is declared
        ondelete='restrict', so dropping the redirect_form template would make
        the upgrade fail when Odoo cleans up stale records.

        The controller and the payment.transaction overrides are removed, so
        this provider CANNOT process a payment. Set it to Disabled before the
        upgrade. Uninstall after go-live, then delete the folder.
    """,
    'depends': [
        'payment',
    ],
    'data': [
        'views/payment_sampath_templates.xml',
        'data/payment_provider_data.xml',
    ],
    'application': False,
    'auto_install': False,
    'installable': True,
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'license': 'LGPL-3',
}
