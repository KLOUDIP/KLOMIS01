# -*- coding: utf-8 -*-
from odoo import fields, models, _, api

class CommentsSelection(models.Model):
    _name = 'comments.selection'

    name = fields.Char(string="Comments")
    section = fields.Selection([
        ('main', 'WS Main Notes'),
        ('fleet', 'WS Fleet Notes'),
        ('product', 'WS Product Notes')], string="Standard Note")
