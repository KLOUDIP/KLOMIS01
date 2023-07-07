# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-TODAY OpenERP S.A. <http://www.odoo.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

{
    'name': 'Odoo Web Client - Kloudip Customisations',
    'version': '0.1',
    'summary': 'Modify some default styling to match Kloudip branding',
    'sequence': '19',
    'category': 'Tools',
    'complexity': 'easy',
    'description':
        """
Odoo Web Client - Kloudip Customisations
========================================
Modify some default styling to match Kloudip branding
        """,
    'data': [
        'data/ir_attachment.xml',
    ],
    'depends': ['web_enterprise'],
    'qweb': [],
    'installable': True,
    'auto_install': False,
    'application': False,

    'assets': {
        'web._assets_primary_variables': [
            (
                "after",
                "web/static/src/legacy/scss/primary_variables.scss",
                "kloudip_web_jsi/static/src/scss/variables_overriden.scss",
            )
        ],

        'web.webclient_bootstrap': [
            (
                "replace",
                "web_enterprise/static/src/img/mobile-icons/android-192x192.png",
                "kloudip_web_jsi/static/src/img/favicon.png",
            )
        ],
        'web.assets_backend': [
            'kloudip_web_jsi/static/src/js/template.js',

        ],
    },
}
