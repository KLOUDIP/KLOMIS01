# -*- coding: utf-8 -*-
"""Drop the removed FIOS Balance field.

The balance was surfaced on the contact form but is not used for any decision
(access is driven by the block-by-days counter), so the field and its column go.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute("""
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = 'res_partner'
           AND column_name = 'fios_balance'
    """)
    if cr.fetchone():
        cr.execute("ALTER TABLE res_partner DROP COLUMN fios_balance")
        _logger.info("FIOS: dropped res_partner.fios_balance")

    cr.execute("""
        DELETE FROM ir_model_fields
         WHERE name = 'fios_balance'
           AND model = 'res.partner'
    """)
