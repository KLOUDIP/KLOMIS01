# -*- coding: utf-8 -*-
# KLOMIS01 v17 -> v19 REMOVAL SHELL - load-only.
from . import models

from odoo.addons.payment import setup_provider, reset_payment_provider


def post_init_hook(env):
    setup_provider(env, 'sampath_int')


def uninstall_hook(env):
    # Kept: this is what resets payment.provider rows back to 'none' when the
    # module is finally uninstalled after go-live.
    reset_payment_provider(env, 'sampath_int')
