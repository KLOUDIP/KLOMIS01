import logging

from odoo import models

_logger = logging.getLogger(__name__)


class IrUiView(models.Model):
    """Force ``delete="False"`` on the views of the restricted models.

    ``ir.ui.view._postprocess_access_rights`` only sets the flag when the arch
    has not set it already::

        for action, operation in (('create', 'create'), ('delete', 'unlink'),
                                  ('edit', 'write')):
            if not node.get(action) and not model.has_access(operation):
                node.set(action, 'False')

    So a view - very often the inline list of a one2many field, written by a
    custom module - that hard-codes ``delete="1"`` keeps showing the trash
    icon even though the user has no unlink right, and clicking it fails with
    an ``AccessError`` on save. This override sets the attribute *before*
    ``super()`` looks at it, so the hard-coded value is overruled for the
    restricted models only, and only for users who lack the right.
    """

    _inherit = "ir.ui.view"

    def _postprocess_access_rights(self, tree):
        try:
            restricted = self.env["ir.model.access"]._kloudip_restricted_models_cached()
        except Exception:  # never break view rendering over this
            _logger.exception("restrict_delete: could not read the restricted models")
            return super()._postprocess_access_rights(tree)

        if restricted:
            # Odoo 19 tags every postprocessed root - including the roots of
            # x2many subviews - with the model it belongs to.
            for node in tree.xpath("//*[@model_access_rights]"):
                if node.tag == "field":
                    continue
                model_name = node.get("model_access_rights")
                if model_name not in restricted or model_name not in self.env:
                    continue
                if not self.env[model_name].has_access("unlink"):
                    node.set("delete", "False")

        return super()._postprocess_access_rights(tree)
