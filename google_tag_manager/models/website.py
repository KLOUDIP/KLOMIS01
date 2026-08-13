from odoo import fields, models

class Website(models.Model):
	_inherit = "website"

	google_tag = fields.Char(string='Google Tag', size=255)
