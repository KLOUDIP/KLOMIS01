# -*- coding: utf-8 -*-

def migrate(cr, version):

   cr.execute("""UPDATE ir_ui_view SET active = false WHERE id = 9771;""")
