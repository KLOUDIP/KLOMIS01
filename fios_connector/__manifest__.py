# -*- encoding: utf-8 -*-

{
    'name': 'FIOS Connector',
    'version': '1.0.6',
    'category': 'Fleet',
    'summery': """FIOS Integration with Odoo""",
    'description': """
        FIOS Integration with Odoo
    """,
    'author': 'Nisus Solutions(PVT) Ltd.',
    'website': 'http://www.nisus.lk',
    'depends': [
        'fleet', 'contacts', 'stock', 'fleet_contract_management'
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/data.xml',
        'views/active_units_views.xml',
        'views/missing_fleets_views.xml',
        'views/missing_serial_views.xml',
        'views/res_partner_views.xml',
        'views/match_fios_missing_views.xml',
        'views/fleet_vehicle_views.xml',
        'views/stock_production_lot_views.xml',
        'views/odoo_unmatched_serials.xml',
        'views/odoo_unmatched_fleets.xml',
    ],
    'installable': True,
    'auto_install': False,
}
