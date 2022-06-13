# -*- encoding: utf-8 -*-

{
    'name': 'FIOS Connector',
    'summary': """FIOS Integration with Odoo""",
    'description': """
FIOS Integration with Odoo
    """,
    'version': '1.0.1',
    'category': 'Fleet',
    'author': 'Nisus Solutions (Pvt) Ltd',
    'website': 'http://www.nisus.lk',
    'depends': [
        'fleet', 'contacts', 'stock', 'fleet_contract_management', 'sale_subscription', 'vehicle_delivery'
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/data.xml',
        'data/server_actions.xml',
        'views/active_units_views.xml',
        'views/missing_fleets_views.xml',
        'views/missing_serial_views.xml',
        'views/res_partner_views.xml',
        'views/match_fios_missing_views.xml',
        'views/fleet_vehicle_views.xml',
        'views/fleet_vehicle_log_contract_views.xml',
        'views/stock_production_lot_views.xml',
        'views/odoo_unmatched_serials.xml',
        'views/odoo_unmatched_fleets.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
# real version : 1.2.6
