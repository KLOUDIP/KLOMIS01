# -*- coding: utf-8 -*-

import base64
import io

from odoo import models
from odoo.tools import str2bool
from odoo.tools.pdf import PdfFileWriter


class IrActionsReport(models.Model):
    """Append the "inside quote" product documents of the subscription lines to
    the quotation PDF.

    In Odoo 17 this was done by monkey-patching
    ``_render_qweb_pdf_prepare_streams`` and rebuilding the whole document
    (header + product documents + body + footer) by hand. That is no longer
    possible: ``sale_pdf_quote_builder`` was rewritten in Odoo 18/19 and the
    ``sale_header`` / ``sale_footer`` binary fields were replaced by the
    ``quotation.document`` model, while product documents are now selected per
    order line through ``product_document_ids``.

    Since ``sale.order.recurring`` lines are not ``sale.order.line`` records,
    they cannot take part in core's assembly loop. Their documents are
    therefore appended after the document produced by core, and their PDF form
    fields are not filled (core prefixes form field names with the sale order
    line id, which these lines do not have).
    """

    _inherit = 'ir.actions.report'

    def _render_qweb_pdf_prepare_streams(self, report_ref, data, res_ids=None):
        result = super()._render_qweb_pdf_prepare_streams(report_ref, data, res_ids=res_ids)
        if self._get_report(report_ref).report_name != 'sale.report_saleorder':
            return result

        always_include = str2bool(self.env['ir.config_parameter'].sudo().get_param(
            'sale.always_include_selected_documents'))

        for order in self.env['sale.order'].browse(res_ids):
            if order.state == 'sale' and not always_include:
                continue

            initial_stream = result.get(order.id, {}).get('stream')
            if not initial_stream:
                continue

            documents = order.sale_order_recurring_ids._get_inside_product_documents()
            if not documents:
                continue

            writer = PdfFileWriter()
            self._add_pages_to_writer(writer, initial_stream.getvalue())
            for document in documents:
                self._add_pages_to_writer(writer, base64.b64decode(document.datas))

            with io.BytesIO() as buffer:
                writer.write(buffer)
                result[order.id].update({'stream': io.BytesIO(buffer.getvalue())})

        return result
