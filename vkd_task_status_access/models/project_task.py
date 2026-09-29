from lxml import etree

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

TASK_STATUS_GROUP = "vkd_task_status_access.group_vkd_task_status_manager"
TASK_STATUS_FIELD = "task_status"  # defined in field_service_worksheet_template
CAN_EDIT_FIELD = "vkd_can_edit_task_status"


class ProjectTask(models.Model):
    _inherit = "project.task"

    vkd_can_edit_task_status = fields.Boolean(
        compute="_compute_vkd_can_edit_task_status",
    )

    @api.depends_context("uid")
    def _compute_vkd_can_edit_task_status(self):
        allowed = self.env.user.has_group(TASK_STATUS_GROUP)
        for task in self:
            task.vkd_can_edit_task_status = allowed

    # ------------------------------------------------------------------
    # UI: make task_status editable for the group, read-only for everyone
    # else, in every project.task form/list view (Project and Field Service,
    # whichever view the field was placed in).
    # ------------------------------------------------------------------
    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type in ("form", "list") and TASK_STATUS_FIELD in self._fields:
            for node in arch.xpath(f"//field[@name='{TASK_STATUS_FIELD}']"):
                # skip fields inside embedded x2many sub-views (other models)
                if node.xpath(
                    "ancestor::field[.//list or .//form or .//kanban]"
                ):
                    continue
                node.set("readonly", f"not {CAN_EDIT_FIELD}")
                node.set("force_save", "1")
                parent = node.getparent()
                if not parent.xpath(f"./field[@name='{CAN_EDIT_FIELD}']"):
                    attr = "column_invisible" if view_type == "list" else "invisible"
                    helper = etree.Element("field", {"name": CAN_EDIT_FIELD, attr: "1"})
                    node.addprevious(helper)
        return arch, view

    # ------------------------------------------------------------------
    # Server-side guard (list multi-edit, import, API, other code paths)
    # ------------------------------------------------------------------
    def _vkd_check_task_status_access(self):
        if self.env.su or self.env.user.has_group(TASK_STATUS_GROUP):
            return
        raise AccessError(_(
            "Only members of the 'Task Status Manager' group can change the Task Status."
        ))

    def _vkd_task_status_changes(self, new_value):
        field = self._fields[TASK_STATUS_FIELD]
        for task in self:
            current = task[TASK_STATUS_FIELD]
            if field.type == "many2one":
                current = current.id
            if (current or False) != (new_value or False):
                return True
        return False

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get(TASK_STATUS_FIELD) for vals in vals_list):
            self._vkd_check_task_status_access()
        return super().create(vals_list)

    def write(self, vals):
        if TASK_STATUS_FIELD in vals and self._vkd_task_status_changes(
            vals[TASK_STATUS_FIELD]
        ):
            self._vkd_check_task_status_access()
        return super().write(vals)
