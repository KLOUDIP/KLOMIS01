# -*- coding: utf-8 -*-
import io
from PyPDF2 import PdfFileWriter
from PyPDF2.generic import NameObject, createStringObject

from odoo import models

from odoo.tools import pdf
from odoo.addons.sale_pdf_quote_builder.models.ir_actions_report import IrActionsReport
from odoo.addons.base.models.ir_actions_report import IrActionsReport as BaseIrActionsReport


_original_render_qweb_pdf_prepare_streams = BaseIrActionsReport._render_qweb_pdf_prepare_streams


def _render_qweb_pdf_prepare_streams(self, report_ref, data, res_ids=None):
    result = _original_render_qweb_pdf_prepare_streams(self, report_ref, data, res_ids=res_ids)
    if self._get_report(report_ref).report_name != 'sale.report_saleorder':
        return result

    orders = self.env['sale.order'].browse(res_ids)

    for order in orders:
        initial_stream = result[order.id]['stream']
        if initial_stream:
            order_template = order.sale_order_template_id
            header_record = order_template if order_template.sale_header else order.company_id
            footer_record = order_template if order_template.sale_footer else order.company_id
            has_header = bool(header_record.sale_header)
            has_footer = bool(footer_record.sale_footer)
            included_product_docs = self.env['product.document']
            doc_line_id_mapping = {}
            for line in order.order_line:
                product_product_docs = line.product_id.product_document_ids
                product_template_docs = line.product_template_id.product_document_ids
                doc_to_include = (
                        product_product_docs.filtered(lambda d: d.attached_on == 'inside')
                        or product_template_docs.filtered(lambda d: d.attached_on == 'inside')
                )
                included_product_docs = included_product_docs | doc_to_include
                doc_line_id_mapping.update({doc.id: line.id for doc in doc_to_include})

            for line in order.sale_order_recurring_ids:
                product_product_docs = line.product_id.product_document_ids
                doc_to_include = product_product_docs.filtered(lambda d: d.attached_on == 'inside')
                included_product_docs = included_product_docs | doc_to_include
                doc_line_id_mapping.update({doc.id: line.id for doc in doc_to_include})

            if (not has_header and not included_product_docs and not has_footer):
                continue

            IrBinary = self.env['ir.binary']
            writer = PdfFileWriter()
            if has_header:
                header_stream = IrBinary._record_to_stream(header_record, 'sale_header').read()
                self._add_pages_to_writer(writer, header_stream)
            if included_product_docs:
                for doc in included_product_docs:
                    doc_stream = IrBinary._record_to_stream(doc, 'datas').read()
                    self._add_pages_to_writer(writer, doc_stream, doc_line_id_mapping[doc.id])
                    if hasattr(self, '_prefix_sol_form_fields'):
                        self._prefix_sol_form_fields(writer=writer, sol_id=doc_line_id_mapping[doc.id])
            self._add_pages_to_writer(writer, (initial_stream).getvalue())
            if has_footer:
                footer_stream = IrBinary._record_to_stream(footer_record, 'sale_footer').read()
                self._add_pages_to_writer(writer, footer_stream)

            form_fields = self._get_form_fields_mapping(order, doc_line_id_mapping)
            pdf.fill_form_fields_pdf(writer, form_fields=form_fields)
            with io.BytesIO() as _buffer:
                writer.write(_buffer)
                stream = io.BytesIO(_buffer.getvalue())
            result[order.id].update({'stream': stream})
    return result


def _prefix_sol_form_fields(self, writer, sol_id):
    prefix = f'{sol_id}_'
    sol_field_names = self._get_sol_form_fields_names()
    if hasattr(writer, 'pages'):
        nbr_pages = len(writer.pages)
    else:  # This method was renamed in PyPDF2 2.0
        nbr_pages = writer.getNumPages()
    for page_id in range(0, nbr_pages):
        page = writer.getPage(page_id)
        if not page.get('/Annots'):
            continue
        for j in range(0, len(page['/Annots'])):
            writer_annot = page['/Annots'][j].getObject()
            if writer_annot.get('/T') in sol_field_names:
                writer_annot.update({
                    NameObject("/T"): createStringObject(prefix + writer_annot.get('/T'))
                })


IrActionsReport._render_qweb_pdf_prepare_streams = _render_qweb_pdf_prepare_streams
if not hasattr(IrActionsReport, '_prefix_sol_form_fields'):
    IrActionsReport._prefix_sol_form_fields = _prefix_sol_form_fields
