from odoo import models, fields, api


class HideMenuUser(models.Model):
    _inherit = 'res.users'

    @api.model_create_multi
    def create(self, vals_list):
        """
        Else the menu will be still hidden even after removing from the list
        """
        # Odoo 19: `clear_caches()` was removed; clear the registry cache instead.
        self.env.registry.clear_cache()
        return super().create(vals_list)

    def _get_is_admin(self):
        """
        The Hide specific menu tab will be hidden for the Admin user form.
        Else once the menu is hidden, it will be difficult to re-enable it.
        """
        admin_id = self.env.ref('base.user_admin').id
        for rec in self:
            rec.is_admin = rec.id == admin_id

    hide_menu_ids = fields.Many2many('ir.ui.menu', string="Menu", store=True,
                                     help='Select menu items that needs to be '
                                          'hidden to this user ')
    is_admin = fields.Boolean(compute=_get_is_admin)

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + [
            'hide_menu_ids',
            'is_admin',
        ]

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + [
            'hide_menu_ids',
            'is_admin',
        ]
