from odoo import models, fields, api, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    google_gtm_key = fields.Char(related='website_id.google_tag')
