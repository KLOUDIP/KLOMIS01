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
    'name': 'Odoo remove sign ad custo',
    'version': '0.1',
    'summary': 'Odoo Kloudip remove sign ad custo',
    'sequence': '19',
    'category': 'Tools',
    'complexity': 'easy',
    'description':
        """
Odoo Customizable WMS Barcode interface
=======================================
Manage field to be editable on package in the WMS interface
        """,
    'data': [
    ],
    'depends': ['sign'],
    'qweb': [],
    'installable': True,
    'auto_install': False,
    'application': True,

    'assets': {
        'sign.assets_common': [
            'remove_ad/static/src/js/widgets.js',
        ],
    },
}
