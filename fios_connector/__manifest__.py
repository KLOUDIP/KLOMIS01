# -*- coding: utf-8 -*-
# KLOMIS01 v17 -> v19 REMOVAL SHELL - load-only, uninstall after go-live.
{
    'name': 'FIOS Connector',
    'summary': "[REMOVAL SHELL] FIOS Integration with Odoo - scheduled for uninstall",
    'description': """
        Load-only shell retained for the 17.0 -> 19.0 upgrade.
        All models and stored fields are preserved so the schema, the
        Studio customisations on res.partner / fleet.vehicle /
        fleet.vehicle.log.contract and any saved filters stay valid.
        Every FIOS API call, view, menu, report and server action override
        has been removed. Uninstall after go-live, then delete the folder.
    """,
    'version': '19.0.2.0.2',
    'category': 'Fleet',
    'author': 'Nisus Solutions (Pvt) Ltd',
    'website': 'http://www.nisus.lk',
    'depends': [
        'base',
        'mail',
        'fleet',
        'stock',
    ],
    'data': [
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
