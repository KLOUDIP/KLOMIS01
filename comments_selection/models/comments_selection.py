# -*- coding: utf-8 -*-
from odoo import fields, models, _, api

class CommentsSelection(models.Model):
    _name = 'comments.selection'

    name = fields.Char(string="Comments")
    section = fields.Selection([
        ('section_one', 'Section One'),
        ('section_two', 'Section Two'),
        ('section_three', 'Section Three')], string="Section")
