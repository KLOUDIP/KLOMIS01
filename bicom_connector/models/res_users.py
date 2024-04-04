import uuid
from odoo import models, fields


class ResUsers(models.Model):
    _inherit = "res.users"

    uuid_token = fields.Char(string="Token")

    def generate_uuid_token(self):
        id = uuid.uuid1()
        self.uuid_token = id.hex
