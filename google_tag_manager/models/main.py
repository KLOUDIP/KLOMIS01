from odoo import fields, models

class AdrollTag(models.Model):
	_name = 'website'
	_inherit = "website"

	google_tag = fields.Char(string='Google Tag', size=255)
