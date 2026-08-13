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
    'version': '19.0.1.0.0',
    'summary': 'Removes the Odoo sign-up advertisement from the Sign Thank You dialog',
    'sequence': '19',
    'category': 'Tools',
    'complexity': 'easy',
    'description':
        """
Odoo Remove Sign Ad
===================
Removes the "Sign Up for free" / "Need to sign documents?" Odoo promotion
banner that is shown to non-authenticated users after they complete signing
a document.
        """,
    'author': "VK Data ApS",
    'website': "https://vkdata.dk",
    'data': [],
    'depends': ['sign'],
    'license': 'OPL-1',
    'application': False,
    'installable': True,
    'auto_install': False,

    'assets': {
        # Backend users signing documents
        'web.assets_backend': [
            'remove_ad/static/src/js/widgets.js',
        ],
        # Public / portal users signing documents (non-authenticated - where ad appears)
        'sign.assets_public_sign': [
            'remove_ad/static/src/js/widgets.js',
        ],
    },
}
