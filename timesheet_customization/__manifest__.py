# -*- coding: utf-8 -*-
# KLOMIS01 v17 -> v19 REMOVAL SHELL - load-only, uninstall after go-live.
{
    'name': 'Timesheet customization',
    'summary': "[REMOVAL SHELL] Employee timesheet modifications - scheduled for uninstall",
    'description': """
        Load-only shell retained for the 17.0 -> 19.0 upgrade.
        Keeps account_analytic_line.start_time / end_time and
        project_task.real_start_time / partner_email so no column is dropped
        before the customer signs off. The timesheet_grid wizard extension,
        the views and the timer override are removed - which also drops the
        timesheet_grid dependency.
    """,
    'version': '19.0.1.0.1',
    'category': 'Services/Timesheets',
    'author': 'Nisus Solutions (Pvt) Ltd',
    'website': 'http://www.nisus.lk',
    'depends': [
        'hr_timesheet',
        'project',
    ],
    'data': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
