# -*- coding: utf-8 -*-
# KLOMIS01 v17 -> v19 REMOVAL SHELL - load-only, uninstall after go-live.
{
    'name': 'SO Assignees',
    'version': '19.0.1.0.2',
    'summary': "[REMOVAL SHELL] SO coordinator assignment - scheduled for uninstall",
    'description': """
        Load-only shell retained for the 17.0 -> 19.0 upgrade.
        Keeps sale_order.coordinator_id, the coordinator.unit.line and
        active.units.monthly tables and hr_employee.coordinator_assigned_ids
        so nothing is dropped and the Studio customisation on hr.employee
        stays valid. All onchange / create validation is removed.

        NOTE: coordinator_id here is NOT the same field as coordination_by_id
        in kloudip_so_coordinator_and_billing_responsible. No data is migrated
        between them.
    """,
    'category': 'Tools',
    'author': 'BitbrainHub',
    'depends': ['sale', 'hr', 'fios_connector'],
    'data': [
        'security/ir.model.access.csv',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
