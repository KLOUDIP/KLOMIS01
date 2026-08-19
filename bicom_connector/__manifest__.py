# -*- coding: utf-8 -*-
# KLOMIS01 v17 -> v19 REMOVAL SHELL - load-only, uninstall after go-live.
{
    "name": "BiCom Connector",
    "author": "Ranga Dharmapriya",
    "website": "",
    "category": "MISC",
    "summary": "[REMOVAL SHELL] BiCom Integration with Odoo - scheduled for uninstall",
    "description": """
        Load-only shell retained for the 17.0 -> 19.0 upgrade.
        Models and fields are preserved so the schema and any Studio
        customisations stay valid; all integration logic is removed.
        Uninstall this module after go-live, then delete the folder.
    """,
    "version": "19.0.1.0.0",
    "depends": [
        'base',
        'voip',
    ],
    "data": [],
    'assets': {},
    "application": False,
    "auto_install": False,
    "installable": True,
    "license": 'LGPL-3',
}
