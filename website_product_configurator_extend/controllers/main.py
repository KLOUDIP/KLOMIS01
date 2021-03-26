from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.addons.website.controllers.main import QueryURL
from werkzeug.exceptions import Forbidden, NotFound
from odoo import fields, http, SUPERUSER_ID, tools, _

class TableCompute(object):

    def __init__(self):
        self.table = {}

    def _check_place(self, posx, posy, sizex, sizey, ppr):
        res = True
        for y in range(sizey):
            for x in range(sizex):
                if posx + x >= ppr:
                    res = False
                    break
                row = self.table.setdefault(posy + y, {})
                if row.setdefault(posx + x) is not None:
                    res = False
                    break
            for x in range(ppr):
                self.table[posy + y].setdefault(x, None)
        return res

    def process(self, products, ppg=20, ppr=4):
        # Compute products positions on the grid
        minpos = 0
        index = 0
        maxy = 0
        x = 0
        for p in products:
            x = min(max(p.website_size_x, 1), ppr)
            y = min(max(p.website_size_y, 1), ppr)
            if index >= ppg:
                x = y = 1

            pos = minpos
            while not self._check_place(pos % ppr, pos // ppr, x, y, ppr):
                pos += 1
            # if 21st products (index 20) and the last line is full (ppr products in it), break
            # (pos + 1.0) / ppr is the line where the product would be inserted
            # maxy is the number of existing lines
            # + 1.0 is because pos begins at 0, thus pos 20 is actually the 21st block
            # and to force python to not round the division operation
            if index >= ppg and ((pos + 1.0) // ppr) > maxy:
                break

            if x == 1 and y == 1:   # simple heuristic for CPU optimization
                minpos = pos // ppr

            for y2 in range(y):
                for x2 in range(x):
                    self.table[(pos // ppr) + y2][(pos % ppr) + x2] = False
            self.table[pos // ppr][pos % ppr] = {
                'product': p, 'x': x, 'y': y,
                'ribbon': p.website_ribbon_id,
            }
            if index <= ppg:
                maxy = max(maxy, y + (pos // ppr))
            index += 1

        # Format table according to HTML needs
        rows = sorted(self.table.items())
        rows = [r[1] for r in rows]
        for col in range(len(rows)):
            cols = sorted(rows[col].items())
            x += len(cols)
            rows[col] = [r[1] for r in cols if r[1]]

        return rows

class ProductConfigWebsiteSale(WebsiteSale):
    @http.route(['/shop/other'], type='http', auth="public", website=True)
    def other_products(self, page=0, ppg=False, **post):

        order = request.website.sale_get_order()
        optional_products = order.order_line.filtered(lambda x: x.config_ok == True).mapped('product_id').mapped('non_compulsory_product_ids').product_tmpl_id
        products = optional_products.filtered(lambda x: x.id not in order.order_line.product_template_id.ids)

        add_qty = int(post.get('add_qty', 1))

        if ppg:
            try:
                ppg = int(ppg)
                post['ppg'] = ppg
            except ValueError:
                ppg = False
        if not ppg:
            ppg = request.env['website'].get_current_website().shop_ppg or 20

        ppr = request.env['website'].get_current_website().shop_ppr or 4

        url = "/shop"

        pricelist_context, pricelist = self._get_pricelist_context()
        request.context = dict(request.context, pricelist=pricelist.id, partner=request.env.user.partner_id)
        product_count = len(products)
        pager = request.website.pager(url=url, total=product_count, page=page, step=ppg, scope=7, url_args=post)
        offset = pager['offset']
        products = products[offset: offset + ppg]

        ProductAttribute = request.env['product.attribute']
        if products:
            # get all products without limit
            attributes = ProductAttribute.search([('product_tmpl_ids', 'in', products.ids)])
        else:
            attributes = []

        category = request.env['product.public.category']

        keep = QueryURL('/shop', category=category and int(category), search="", attrib=[],
                        order=post.get('order'))

        values = {
            'pricelist': pricelist,
            'add_qty': add_qty,
            'products': products,
            'pager':pager,
            'search_count': product_count,  # common for all searchbox
            'bins': TableCompute().process(products, ppg, ppr),
            'ppg': ppg,
            'ppr': ppr,
            'keep': keep,
            'attributes': attributes,
        }
        return request.render("website_product_configurator_extend.other_products", values)

    @http.route(['/shop/checkout'], type='http', auth="public", website=True, sitemap=False)
    def checkout(self, **post):
        order = request.website.sale_get_order()
        mandatory_items = self.get_mandatory_products(order)
        if len(mandatory_items) > 0:
            return request.redirect("%s?mandatory_items_available=1" % '/shop/cart')
        rec = super(ProductConfigWebsiteSale, self).checkout()
        return rec

    @http.route(['/shop/cart'], type='http', auth="public", website=True, sitemap=False)
    def cart(self, access_token=None, revive='', **post):

        order = request.website.sale_get_order()
        if order and order.state != 'draft':
            request.session['sale_order_id'] = None
            order = request.website.sale_get_order()
        values = {}
        if access_token:
            abandoned_order = request.env['sale.order'].sudo().search([('access_token', '=', access_token)], limit=1)
            if not abandoned_order:  # wrong token (or SO has been deleted)
                raise NotFound()
            if abandoned_order.state != 'draft':  # abandoned cart already finished
                values.update({'abandoned_proceed': True})
            elif revive == 'squash' or (revive == 'merge' and not request.session.get(
                    'sale_order_id')):  # restore old cart or merge with unexistant
                request.session['sale_order_id'] = abandoned_order.id
                return request.redirect('/shop/cart')
            elif revive == 'merge':
                abandoned_order.order_line.write({'order_id': request.session['sale_order_id']})
                abandoned_order.action_cancel()
            elif abandoned_order.id != request.session.get(
                    'sale_order_id'):  # abandoned cart found, user have to choose what to do
                values.update({'access_token': abandoned_order.access_token})

        values.update({
            'website_sale_order': order,
            'date': fields.Date.today(),
            'suggested_products': [],
            'mandatory_products': [],
            'non_compulsory_product_ids': [],
        })
        if order:
            order.order_line.filtered(lambda l: not l.product_id.active).unlink()
            _order = order
            if not request.env.context.get('pricelist'):
                _order = order.with_context(pricelist=order.pricelist_id.id)
            values['non_compulsory_product_ids'] = self.get_non_compulsory_products(_order)
            values['mandatory_products'] = self.get_mandatory_products(_order)
            values['suggested_products'] = _order._cart_accessories()

        if post.get('type') == 'popover':
            # force no-cache so IE11 doesn't cache this XHR
            return request.render("website_sale.cart_popover", values, headers={'Cache-Control': 'no-cache'})

        return request.render("website_sale.cart", values)

    def get_mandatory_products(self, order):
        products = order.order_line.filtered(lambda x: x.config_ok == True).product_id.mapped('compulsory_product_ids').mapped('product_tmpl_id').filtered(lambda x: x.id not in order.order_line.product_template_id.ids)
        # product_tmpl_ids = products.mapped('product_tmpl_id')
        return products

    def get_non_compulsory_products(self, order):
        products = order.order_line.filtered(lambda x: x.config_ok == True).product_id.mapped('non_compulsory_product_ids').mapped('product_tmpl_id').filtered(lambda x: x.id not in order.order_line.product_template_id.ids)
        # product_tmpl_ids = products.mapped('product_tmpl_id')
        return products

    @http.route(['/shop/cart/update_json'], type='json', auth="public", methods=['POST'], website=True, csrf=False)
    def cart_update_json(self, product_id, line_id=None, add_qty=None, set_qty=None, display=True):
        rec = super(ProductConfigWebsiteSale, self).cart_update_json(product_id, line_id, add_qty, set_qty, display)
        # order = request.website.sale_get_order(force_create=1)
        # if order.state != 'draft':
        #     request.website.sale_reset()
        #     return {}
        #
        # value = order._cart_update(product_id=product_id, line_id=line_id, add_qty=add_qty, set_qty=set_qty)

        # if not order.cart_quantity:
        #     request.website.sale_reset()
        #     return value

        order = request.website.sale_get_order()
        rec['cart_quantity'] = order.cart_quantity

        if not display:
            return rec

        rec['website_sale.cart_lines'] = request.env['ir.ui.view']._render_template("website_sale.cart_lines", {
            'website_sale_order': order,
            'date': fields.Date.today(),
            'suggested_products': order._cart_accessories(),
            'mandatory_products': self.get_mandatory_products(order)
        })
        rec['website_sale.short_cart_summary'] = request.env['ir.ui.view']._render_template(
            "website_sale.short_cart_summary", {
                'website_sale_order': order,
            })
        return rec