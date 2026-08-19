# -*- coding: utf-8 -*-
# KLOMIS01 v17 -> v19 REMOVAL SHELL - load-only, uninstall after go-live.
{
    'name': 'FIOS Connector Active Unit Report',
    'summary': "[REMOVAL SHELL] FIOS active units report - scheduled for uninstall",
    'description': """
        Load-only shell retained for the 17.0 -> 19.0 upgrade.
        Only action_fios_active_units_send() survives, as a stub, because a
        Studio customisation on the Contacts form has a button bound to it.
        The report, wizard and mail template are removed.
        Uninstall after go-live, then delete the folder.
    """,
    'version': '19.0.1.0.1',
    'category': 'Fleet',
    'author': 'Ranga Dharmapriya',
    'website': '',
    'depends': ['fios_connector'],
    'data': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
