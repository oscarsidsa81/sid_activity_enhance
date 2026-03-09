from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleActivity(models.Model):
    _inherit = 'sale.activity'

    # Mantener la mecánica original: el campo operativo clave sigue siendo
    # picking_type_id. Añadimos una referencia real y campos auxiliares, pero
    # no desplazamos el comportamiento base de oct_so_line_info.
    name = fields.Char(
        string='Referencia',
        default=lambda self: self.env['ir.sequence'].sudo().next_by_code('sale.activity'),
        readonly=True,
        copy=False,
    )
    type = fields.Selection (
        selection_add=[
            ('colada', 'COLADA'),
        ],
        ondelete={'colada' : 'set null'},
    )
    sid_item = fields.Char(string='Item', related='sale_line_id.item', store=True, readonly=True)
    sid_qty = fields.Float(string='Cantidad solicitada', related='sale_line_id.product_uom_qty', store=False, readonly=True)
    sid_peso = fields.Float(string='Peso unitario', related='product_id.weight', store=False, readonly=True)
    sid_peso_total = fields.Float(string='Peso total', compute='_compute_weight_fields', store=False, readonly=True)
    sid_desc_sale_line = fields.Text(string='Descripción venta', related='sale_line_id.name', store=False, readonly=True)
    sid_fecha_venta = fields.Datetime(string='Fecha contractual venta', related='sale_line_id.calculated_date', store=True, readonly=True)

    TAG_NAME_MAP = {
        'mecanizar': 'MECANIZAR',
        'cortar': 'CORTAR',
        'roscar': 'ROSCAR',
        'biselar': 'BISELAR',
        'ranurar': 'RANURAR',
        'pintar': '3LPE / PINTAR',
        'curvar': 'CURVAR',
        'galvanizar': 'GALVANIZAR',
        'ensayos': 'ENSAYOS',
        'montaje': 'MONTAJE',
        'inspeccion interna': 'INSPECCION INTERNA',
        'inspeccion cliente': 'INSPECCION CLIENTE',
        'inspeccion': 'INSPECCION',
        'taller': 'TALLER',
    }

    @api.depends(
        'sid_qty',
        'sid_peso',
    )
    def _compute_weight_fields(self):
        for record in self :
            record['sid_peso_total'] = record.sid_peso * record.sid_qty

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence'].sudo()
        for vals in vals_list:
            if not vals.get('name'):
                vals['name'] = seq.next_by_code('sale.activity')
        records = super().create(vals_list)
        records._autofill_picking_type_from_route()
        records._check_duplicate_activity()
        records._check_route_vs_picking_type()
        records._sync_activity_tags()
        return records

    def write(self, vals):
        old_sale_lines = self.mapped('sale_line_id') if {'sale_line_id', 'type'}.intersection(vals.keys()) else self.env['sale.order.line']
        res = super().write(vals)
        if {'sale_line_route', 'picking_type_id'}.intersection(vals.keys()):
            self._autofill_picking_type_from_route()
            self._check_route_vs_picking_type()
        if {'sale_line_id', 'type'}.intersection(vals.keys()):
            self._check_duplicate_activity()
            self._sync_activity_tags(extra_sale_lines=old_sale_lines)
        return res

    def unlink(self):
        sale_lines = self.mapped('sale_line_id')
        res = super().unlink()
        self._recompute_sale_line_and_inventory_tags(sale_lines)
        return res

    def _check_duplicate_activity(self):
        for rec in self.filtered(lambda r: r.sale_line_id and r.type):
            dup = self.search([
                ('id', '!=', rec.id),
                ('sale_line_id', '=', rec.sale_line_id.id),
                ('type', '=', rec.type),
            ], limit=1)
            if dup:
                raise UserError(_(
                    'Este item %s ya tiene una actividad del tipo %s. '
                    'Incluye en la descripción de la actividad todos los trabajos relacionados.'
                ) % ((rec.sid_item or rec.sale_line_id.display_name or ''), rec.type))

    def _get_route_certificate_picking_type(self):
        self.ensure_one()
        route = self.sale_line_route
        if not route:
            return self.env['stock.picking.type']
        rules = route.rule_ids.sorted(lambda r: (r.sequence, r.id))
        cert_rules = rules.filtered(lambda r: r.picking_type_id and getattr(r.picking_type_id, 'is_certificate_type', False))
        return cert_rules[:1].mapped('picking_type_id')

    def _autofill_picking_type_from_route(self):
        # Rebase: respetar la mecánica histórica centrada en certificados.
        # Solo autocompletamos cuando la ruta contemple un picking_type marcado
        # como `is_certificate_type`. Si no existe, dejamos el valor tal como esté.
        for rec in self.filtered(lambda r: r.sale_line_route and not r.picking_type_id):
            picking_type = rec._get_route_certificate_picking_type()
            if picking_type:
                rec.picking_type_id = picking_type.id

    def _check_route_vs_picking_type(self):
        Route = self.env['stock.location.route'].sudo()
        for rec in self.filtered(lambda r: r.picking_type_id and r.sale_line_route):
            allowed_routes = Route.search([('rule_ids.picking_type_id', '=', rec.picking_type_id.id)])
            if rec.sale_line_route not in allowed_routes:
                raise UserError(_(
                    "Ojo, indicar un tipo de operación acorde a la ruta. Ruta '%s' no contempla '%s'."
                ) % (rec.sale_line_route.display_name, rec.picking_type_id.display_name))

    def _sync_activity_tags(self, extra_sale_lines=None):
        sale_lines = self.mapped('sale_line_id')
        if extra_sale_lines:
            sale_lines |= extra_sale_lines
        self._recompute_sale_line_and_inventory_tags(sale_lines)

    def _resolve_tag_ids_for_types(self, activity_types):
        Tag = self.env['sid.activity.tag'].sudo()
        Rule = self.env['sale.activity.tag.rule'].sudo()
        tag_ids = set()
        for act_type in [t for t in activity_types if t]:
            rule = Rule.search([('active', '=', True), ('activity_type', '=', act_type)], limit=1)
            if rule and rule.sid_tag_id:
                tag_ids.add(rule.sid_tag_id.id)
                continue
            tag = Tag.search([('code', '=', act_type)], limit=1)
            if not tag:
                tag = Tag.search([('name', '=ilike', self.TAG_NAME_MAP.get(act_type, act_type))], limit=1)
            if tag:
                tag_ids.add(tag.id)
        return sorted(tag_ids)

    def _recompute_sale_line_and_inventory_tags(self, sale_lines):
        if not sale_lines:
            return
        Activity = self.env['sale.activity'].sudo()
        Move = self.env['stock.move'].sudo()
        for line in sale_lines.sudo():
            acts = Activity.search([('sale_line_id', '=', line.id)])
            tag_ids = self._resolve_tag_ids_for_types(acts.mapped('type'))
            if 'sid_activity_tag_ids' in line._fields:
                line.write({'sid_activity_tag_ids': [(6, 0, tag_ids)]})
            moves = Move.search([('sale_line_id', '=', line.id)]) if 'sale_line_id' in Move._fields else Move.browse()
            if moves and 'sid_activity_tag_ids' in Move._fields:
                moves.write({'sid_activity_tag_ids': [(6, 0, tag_ids)]})

    # TODO esto parece que no se usa, hay q ver el cambio de estados de sale.activity
    def action_mark_done(self):
        self.write({'stage': 'done'})
        return True
