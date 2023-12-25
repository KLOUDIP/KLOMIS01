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
    'name': 'Kloudip link vehicle with delivery',
    'version': '16.0.2.0.0',
    'summary': 'Odoo Kloudip Custom module',
    'sequence': '19',
    'category': 'Tools',
    'complexity': 'easy',
    'description':
        """
Odoo Custom Module
==================
Kloudip link vehicle with delivery
        """,
    'data': [
        'models/stock.xml',
        'views/stock.xml',
        'models/fleet.xml',
        'views/fleet.xml',
        'actions/server_actions.xml',
             ],
    'depends': [
        'stock',
        'fleet',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'LGPL-3',
}
