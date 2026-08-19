# -*- coding: utf-8 -*-
# KLOMIS01 v17 -> v19 REMOVAL SHELL - load-only, uninstall after go-live.
{
    'name': "Google tag Manager",
    'version': "19.0.3.0.2",
    'author': "Nisus Solutions (Pvt) Ltd",
    'category': "Web",
    'summary': "[REMOVAL SHELL] Google tag on Website - scheduled for uninstall",
    'description': """
        Load-only shell retained for the 17.0 -> 19.0 upgrade.
        Keeps website.google_tag so the stored key is not lost before the
        customer signs off on it. The layout templates were already disabled
        in 17.0 and the hardcoded pre-migration script has been dropped.
        Uninstall after go-live, then delete the folder.
    """,
    'license': 'OPL-1',
    'website': 'http://www.nisus.lk/',
    'depends': ['website'],
    'data': [],
    'demo': [],
    'images': [],
    'application': False,
    'auto_install': False,
    'installable': True,
}
