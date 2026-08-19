from odoo import _, api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    trazet_product_key = fields.Selection(
        selection=[
            ('users', 'Users'),
            ('geofences', 'Geofences'),
            ('reports', 'Reports'),
            ('notifications', 'Notifications'),
            ('devices', 'Devices'),
            ('devicesGroups', 'Devices Groups'),
            ('drivers', 'Drivers'),
            ('commands', 'Commands'),
            ('collectPeriod', '365 Days History'),
            ('allowExternalAPI', 'API Access'),
        ],
        string='Trazet Product Key',
        help='Key used to identify this product in Trazet API (e.g., users, devices, geofences)',
    )
