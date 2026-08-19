# -*- coding: utf-8 -*-
from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    fios_tier_id = fields.Many2one(
        'fios.service.tier',
        string='FIOS Service Tier',
        help="Which FIOS tier (FIOS / Lite / Premium) this product belongs to. "
             "The account is provisioned under this tier's token when purchased.",
    )

    fios_plan_code = fields.Char(
        string='FIOS Plan Code',
        help="Deprecated in favour of the tier's plan code. Kept for reference; "
             "the billing plan now comes from fios_tier_id.plan_code.",
    )

    fios_service = fields.Selection(
        selection=[
            ('avl_unit', 'Units / Devices'),
            ('storage_user', 'Users'),
            ('zones_library', 'Geofences'),
            ('own_google_service', 'Google Maps'),
            ('ecodriving', 'Ecodriving'),
            ('avl_retranslator', 'Data Streaming'),
        ],
        string='FIOS Service',
        help="FIOS billing service this product provisions. Quantity services "
             "(units/users/geofences) use the subscribed quantity as the limit; "
             "feature services (Google Maps, Ecodriving, Data Streaming) are "
             "enabled when purchased and disabled when removed.",
    )

    is_fios_free_plan = fields.Boolean(
        string='Is FIOS Free Plan?',
        help='If set, this product is included in the free subscription that is '
             'auto-created for a new FIOS customer.',
    )