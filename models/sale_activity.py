from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleActivity(models.Model):
    _inherit = 'sale.activity'

    _rec_name = 'name'

    name = fields.Char(
        string='Referencia',
        default=lambda self: self.env['ir.sequence'].sudo().next_by_code('sale.activity'),
        readonly=True,
        copy=False,
    )

    # Campos operativos (NO Studio). Si existen campos legacy x_* se usan
    # SOLO como fallback para no perder información histórica.
    sid_item = fields.Char(string='Item', compute='_compute_sid_fields', store=True, readonly=True)
    sid_qty = fields.Float(string='Cantidad solicitada', compute='_compute_sid_fields', store=True, readonly=True)
    sid_peso = fields.Float(string='Peso unitario', compute='_compute_sid_fields', store=True, readonly=True)
    sid_peso_total = fields.Float(string='Peso total', compute='_compute_sid_fields', store=True, readonly=True)
    sid_desc_sale_line = fields.Text(string='Descripción venta', compute='_compute_sid_fields', store=True, readonly=True)
    sid_fecha_venta = fields.Datetime(string='Fecha contractual venta', compute='_compute_sid_fields', store=True, readonly=True)

    @api.depends('sale_line_id', 'sale_line_id.product_uom_qty', 'sale_line_id.name', 'sale_line_id.sequence',
                 'sale_line_id.order_id.date_order', 'sale_line_id.order_id.commitment_date', 'product_id', 'product_id.weight')
    def _compute_sid_fields(self):
        for rec in self:
            line = rec.sale_line_id
            # Item
            item = False
            if 'x_item' in rec._fields and rec.x_item:
                item = rec.x_item
            elif line:
                item = str(getattr(line, 'sequence', False) or line.id)
            rec.sid_item = item or ''

            # Qty
            qty = 0.0
            if 'x_qty' in rec._fields and rec.x_qty:
                qty = rec.x_qty
            elif line and 'product_uom_qty' in line._fields:
                qty = line.product_uom_qty or 0.0
            rec.sid_qty = qty

            # Peso unitario
            peso = 0.0
            if 'x_peso' in rec._fields and rec.x_peso:
                peso = rec.x_peso
            elif rec.product_id and 'weight' in rec.product_id._fields and rec.product_id.weight:
                peso = rec.product_id.weight
            rec.sid_peso = peso
            rec.sid_peso_total = peso * qty

            # Descripción venta
            desc = False
            if 'x_desc_sale_line' in rec._fields and rec.x_desc_sale_line:
                desc = rec.x_desc_sale_line
            elif line and 'name' in line._fields:
                desc = line.name
            rec.sid_desc_sale_line = desc or ''

            # Fecha venta
            fecha = False
            if 'x_fecha_venta' in rec._fields and rec.x_fecha_venta:
                fecha = rec.x_fecha_venta
            elif line and line.order_id:
                fecha = getattr(line.order_id, 'commitment_date', False) or getattr(line.order_id, 'date_order', False)
            rec.sid_fecha_venta = fecha

    # activity_type normalizado -> código estable del tag
    TAG_CODE_MAP = {
        'mecanizar': 'mecanizar',
        'cortar': 'cortar',
        'roscar': 'roscar',
        'biselar': 'biselar',
        'ranurar': 'ranurar',
        'pintar': 'pintar',
        'curvar': 'curvar',
        'galvanizar': 'galvanizar',
        'ensayos': 'ensayos',
        'montaje': 'montaje',
        'inspeccion interna': 'inspeccion interna',
        'inspeccion cliente': 'inspeccion cliente',
        'inspeccion': 'inspeccion',
        'taller': 'taller',
    }


    @staticmethod
    def _normalize_activity_type(raw):
        value = (raw or '').strip().lower()
        return value.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence'].sudo()
        for vals in vals_list:
            # Use a real field for the reference instead of writing to `display_name`
            if not vals.get('name'):
                vals['name'] = seq.next_by_code('sale.activity')
        records = super().create(vals_list)
        records._autofill_picking_type_from_route()
        records._check_duplicate_activity()
        records._check_route_vs_picking_type()
        records._sync_activity_tags()
        return records

    def write(self, vals):
        old_sale_lines = self.env['sale.order.line']
        if {'sale_line_id', 'type'}.intersection(vals.keys()):
            old_sale_lines = self.mapped('sale_line_id')

        res = super().write(vals)

        relevant_dup = {'sale_line_id', 'type'}
        relevant_route = {'picking_type_id', 'sale_line_route', 'type'}
        relevant_tags = {'type', 'sale_line_id'}

        if relevant_route.intersection(vals.keys()):
            self._autofill_picking_type_from_route()
        if relevant_dup.intersection(vals.keys()):
            self._check_duplicate_activity()
        if relevant_route.intersection(vals.keys()):
            self._check_route_vs_picking_type()
        if relevant_tags.intersection(vals.keys()):
            self._sync_activity_tags(extra_sale_lines=old_sale_lines)
        return res

    def unlink(self):
        affected_sale_lines = self.mapped('sale_line_id')
        res = super().unlink()
        self._recompute_sale_line_and_inventory_tags(affected_sale_lines)
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
                    "Este item %s ya tiene una actividad del tipo %s. "
                    "Incluye en la descripción de la actividad todos los trabajos relacionados."
                ) % ((rec.sid_item or rec.sale_line_id.display_name or ''), rec.type))

    def _is_certificate_related(self):
        self.ensure_one()
        activity_type = self._normalize_activity_type(self.type)
        return any(term in activity_type for term in {'cert', 'certificado', 'certificados', 'ensayo', 'ensayos', 'inspeccion'})

    def _get_route_picking_type_candidates(self):
        self.ensure_one()
        if not self.sale_line_route:
            return self.env['stock.picking.type']
        return self.sale_line_route.sudo().rule_ids.mapped('picking_type_id').sorted(key=lambda pt: (pt.sequence, pt.id))

    def _pick_certificate_operation_type(self, candidates):
        """Elige tipo de operación por booleano `is_certificate_type` cuando exista."""
        if not candidates:
            return candidates

        if 'is_certificate_type' in candidates._fields:
            cert_candidates = candidates.filtered('is_certificate_type')
            if cert_candidates:
                return cert_candidates[:1]

        preferred = candidates.filtered(lambda c: c.code == 'internal')[:1]
        if preferred:
            return preferred
        preferred = candidates.filtered(lambda c: c.code == 'outgoing')[:1]
        return preferred or candidates[:1]

    def _autofill_picking_type_from_route(self):
        for rec in self.filtered(lambda r: r.sale_line_route and not r.picking_type_id and r._is_certificate_related()):
            candidates = rec._get_route_picking_type_candidates()
            chosen = rec._pick_certificate_operation_type(candidates)
            if chosen:
                rec.picking_type_id = chosen.id

    def _check_route_vs_picking_type(self):
        Route = self.env['stock.location.route'].sudo()
        for rec in self.filtered(lambda r: r.picking_type_id and r.sale_line_route):
            allowed_routes = Route.search([('rule_ids.picking_type_id', '=', rec.picking_type_id.id)])
            if rec.sale_line_route not in allowed_routes:
                raise UserError(_(
                    "Ojo, indicar un tipo de operación acorde a la ruta. "
                    "Ruta '%s' no contempla '%s'."
                ) % (rec.sale_line_route.display_name, rec.picking_type_id.display_name))

    def _sync_activity_tags(self, extra_sale_lines=None):
        sale_lines = self.mapped('sale_line_id')
        if extra_sale_lines:
            sale_lines |= extra_sale_lines
        self._recompute_sale_line_and_inventory_tags(sale_lines)

    def _get_tag_model(self):
        # Modelo estable propio del módulo (no depende de Studio)
        return 'sid.activity.tag'

    def _resolve_tag_ids_for_types(self, activity_types):
        tag_model = self._get_tag_model()
        if not tag_model:
            return self.env['ir.model'], []

        Tag = self.env[tag_model].sudo()
        Rule = self.env['sale.activity.tag.rule'].sudo()

        raw_types = [t for t in activity_types if t]

        result = set()
        rules = Rule.browse()
        if raw_types:
            rules = Rule.search([
                ('active', '=', True),
                ('activity_type', 'in', list(set(raw_types))),
            ])
            result.update(rules.mapped('tag_id').ids)

        # Fallback: resolver por code (sin IDs duros) si no existe regla
        unresolved = set(raw_types) - set(rules.mapped('activity_type'))
        for raw in unresolved:
            normalized = self._normalize_activity_type(raw)
            wanted_code = self.TAG_CODE_MAP.get(normalized)
            if not wanted_code:
                continue
            tag = Tag.search([('code', '=', wanted_code)], limit=1)
            if tag:
                result.add(tag.id)

        return Tag, sorted(result)

    def _recompute_sale_line_and_inventory_tags(self, sale_lines):
        if not sale_lines:
            return

        for line in sale_lines.sudo():
            activity_types = line.activity_ids.mapped('type') if 'activity_ids' in line._fields else []
            Tag, tag_ids = self._resolve_tag_ids_for_types(activity_types)
            if not Tag:
                continue
            if 'sid_activity_tag_ids' in line._fields:
                line.write({'sid_activity_tag_ids': [(6, 0, tag_ids)]})
            self._sync_inventory_tags_from_sale_line(line, tag_ids, Tag._name)

    def _sync_inventory_tags_from_sale_line(self, sale_line, tag_ids, tag_model):
        moves = self.env['stock.move']
        if 'move_ids' in sale_line._fields:
            moves |= sale_line.move_ids
        if not moves:
            return

        if 'sid_activity_tag_ids' in moves._fields:
            moves.sudo().write({'sid_activity_tag_ids': [(6, 0, tag_ids)]})

        # No escribimos en picking: el resumen a nivel albarán es compute (no store).