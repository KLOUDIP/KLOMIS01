# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------------
# KLOMIS01 v17 -> v19 REMOVAL SHELL — pre-migration
#
# Lives in migrations/0.0.0/, so Odoo runs it on every version change, and
# 0.0.0 pre- scripts are ordered FIRST within the pre stage
# (odoo/modules/migration.py: _get_migration_versions).
#
# WHY THIS EXISTS
# ---------------
# The shells ship no ir.ui.view records, but the 17.0 view records are still
# sitting in the database when the upgrade starts. Odoo only removes stale
# module records at the very END of the load (ir.model.data._process_end), so
# until then those views are live and are still combined into their model's
# form view and validated. The 19.0 upgrade aborted on exactly that:
#
#   ParseError: while parsing contact_restriction/views/res_partner_views.xml
#   Error while validating view near: <form string="Partners">
#     - field "subscription_count" does not exist in model "res.partner"
#     - element "<page name='active_units' ... >"
#
# That page belongs to fios_connector. contact_restriction inherits the same
# base res.partner form, so validating contact_restriction's view validated
# the stale FIOS page with it — and subscription_count is gone in 19.0.
#
# WHAT IT DOES  (idempotent; the same script is in all seven shells, so
# whichever one Odoo loads first does the work and the rest are no-ops)
#
#   1. Deactivates every ir.ui.view owned by the seven modules. Inactive views
#      are skipped when Odoo walks the inheritance tree, so they can no longer
#      fail validation — and neither can anything inheriting them.
#   2. Deactivates their menus, so UAT does not show FIOS menus backed by
#      views that no longer render.
#   3. Marks their remaining records noupdate, so the end-of-load cleanup does
#      NOT delete them during the upgrade. Deleting a view cascades to every
#      view inheriting it, Studio customisations included, and that is not a
#      thing to have happen silently in the middle of an upgrade.
#
# Nothing here is permanent. button_immediate_uninstall() after go-live
# removes all of it properly, in one deliberate step, with sign-off.
# ---------------------------------------------------------------------------
import logging

_logger = logging.getLogger(__name__)

MODULES = (
    'bicom_connector',
    'fios_connector',
    'fios_connector_report',
    'google_tag_manager',
    'payment_sampath_int',
    'so_assignees',
    'timesheet_customization',
)

# Record types the end-of-load cleanup would delete and that can cascade.
# ir.model / ir.model.fields / ir.model.access are deliberately NOT frozen —
# Odoo manages those itself and the shells still declare their ACLs.
# Views the shells STILL ship, so they are not stale and must stay active.
# payment_sampath_int.redirect_form is the one that matters:
# payment.provider.redirect_form_view_id is ondelete='restrict'.
KEEP_ACTIVE = (('payment_sampath_int', 'redirect_form'),)

FREEZE_MODELS = (
    'ir.ui.view',
    'ir.ui.menu',
    'ir.actions.act_window',
    'ir.actions.act_window.view',
    'ir.actions.report',
    'ir.actions.server',
    'ir.actions.client',
    'ir.cron',
    'mail.template',
)


def migrate(cr, version):
    # `version` is falsy on a fresh install — nothing stale to clean up.
    if not version:
        return

    cr.execute("""
        UPDATE ir_ui_view v
           SET active = false
          FROM ir_model_data d
         WHERE d.model  = 'ir.ui.view'
           AND d.res_id = v.id
           AND d.module IN %s
           AND (d.module, d.name) NOT IN %s
           AND v.active
    """, (MODULES, KEEP_ACTIVE))
    views = cr.rowcount

    cr.execute("""
        UPDATE ir_ui_menu m
           SET active = false
          FROM ir_model_data d
         WHERE d.model  = 'ir.ui.menu'
           AND d.res_id = m.id
           AND d.module IN %s
           AND m.active
    """, (MODULES,))
    menus = cr.rowcount

    cr.execute("""
        UPDATE ir_model_data
           SET noupdate = true
         WHERE module IN %s
           AND model  IN %s
           AND COALESCE(noupdate, false) = false
    """, (MODULES, FREEZE_MODELS))
    frozen = cr.rowcount

    if views or menus or frozen:
        _logger.info(
            "KLOMIS01 removal shells: deactivated %s view(s) and %s menu(s), "
            "froze %s record(s) against end-of-load cleanup, for modules %s",
            views, menus, frozen, ', '.join(MODULES),
        )
    else:
        _logger.info("KLOMIS01 removal shells: nothing left to freeze (already done).")
