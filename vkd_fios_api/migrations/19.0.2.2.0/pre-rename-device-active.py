# -*- coding: utf-8 -*-
"""Rename fios_device.active -> fios_device.device_active.

`active` is Odoo's magic archive field: every device FIOS reported as
deactivated was stored with active = false and then filtered out of
partner.fios_device_ids, so the contact form only ever listed activated
devices. Renaming the column keeps the existing values and takes the records
out of the archive mechanism.

Runs pre-install so the ORM finds the column already populated instead of
adding an empty device_active alongside an orphaned active.
"""
import logging

_logger = logging.getLogger(__name__)


def _has_column(cr, table, column):
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = %s AND column_name = %s
    """, (table, column))
    return bool(cr.fetchone())


def migrate(cr, version):
    if not version:
        return

    if not _has_column(cr, 'fios_device', 'active'):
        _logger.info("FIOS: fios_device.active already renamed, nothing to do")
        return

    if _has_column(cr, 'fios_device', 'device_active'):
        # Both present (a partial upgrade): keep the archive column's values.
        cr.execute("UPDATE fios_device SET device_active = active")
        cr.execute("ALTER TABLE fios_device DROP COLUMN active")
    else:
        cr.execute("ALTER TABLE fios_device RENAME COLUMN active TO device_active")

    cr.execute("UPDATE fios_device SET device_active = TRUE WHERE device_active IS NULL")

    cr.execute("""
        UPDATE ir_model_fields
           SET name = 'device_active'
         WHERE name = 'active' AND model = 'fios.device'
    """)

    cr.execute("SELECT COUNT(*) FROM fios_device WHERE device_active = FALSE")
    _logger.info("FIOS: renamed fios_device.active -> device_active; "
                 "%s previously hidden deactivated device(s) are now visible",
                 cr.fetchone()[0])
