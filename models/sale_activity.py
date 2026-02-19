from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleActivity(models.Model):
    _inherit = 'sale.activity'

    TAG_ID_MAP = {
        'mecanizar': 15,
        'cortar': 1,
        'roscar': 16,
        'biselar': 17,
        'ranurar': 18,
        '3lpe / pintar': 19,
        'pintar': 19,
        'curvar': 20,
        'galvanizar': 21,
        'ensayos': 22,
        'montaje': 23,
        'certificados': 24,
        'inspeccion interna': 24,
        'inspección interna': 24,
        'inspeccion cliente': 25,
        'inspección cliente': 25,
        'inspeccion': 26,
        'inspección': 26,
        'taller': 27,
        'colada': 29,
        'coladas': 29,
    }

    x_desc_sale_line = fields.Text(string='Descripción Venta', related='sale_line_id.name', readonly=True, store=False)
    x_fecha_venta = fields.Datetime(string='Fecha Contractual Venta', related='sale_line_id.calculated_date', readonly=True, store=True)
    x_item = fields.Char(string='Item', related='sale_line_id.item', readonly=True, store=True)
    x_peso = fields.Float(string='Peso unitario', related='product_id.weight', readonly=True, store=False)
    x_qty = fields.Float(string='Cantidad Solicitada', related='sale_line_id.product_uom_qty', readonly=True, store=True)
    x_peso_total = fields.Float(string='Peso Total', compute='_compute_x_peso_total', store=True, readonly=True)

    @api.depends('x_qty', 'x_peso')
    def _compute_x_peso_total(self):
        for rec in self:
            rec.x_peso_total = (rec.x_peso or 0.0) * (rec.x_qty or 0.0)

    @staticmethod
    def _normalize_activity_type(raw):
        value = (raw or '').strip().lower()
        return value.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence'].sudo()
        for vals in vals_list:
            if not vals.get('display_name'):
                vals['display_name'] = seq.next_by_code('sale.activity')
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
                ) % (dup.x_item or rec.x_item or '', rec.type))

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
        field = self.env['sale.order.line']._fields.get('x_sale_line_tags')
        if not field or field.type != 'many2many':
            return False
        return field.comodel_name

    def _resolve_tag_ids_for_types(self, activity_types):
        tag_model = self._get_tag_model()
        if not tag_model:
            return self.env['ir.model'], []

        Tag = self.env[tag_model].sudo()
        Rule = self.env['sale.activity.tag.rule'].sudo()

        normalized_types = []
        for activity_type in activity_types:
            normalized = self._normalize_activity_type(activity_type)
            if normalized:
                normalized_types.append(normalized)

        result = set()
        rules = Rule.browse()
        if normalized_types:
            rules = Rule.search([
                ('active', '=', True),
                ('activity_type', 'in', list(set(normalized_types))),
            ])
            result.update(rules.mapped('tag_id').ids)

        # Fallback heredado: resolver por nombre o mapa estático si no existe regla
        unresolved = set(normalized_types) - set(rules.mapped('activity_type'))

        for normalized in unresolved:
            tag = Tag.search([('name', '=ilike', normalized)], limit=1)
            if tag:
                result.add(tag.id)
                continue

            fallback = self.TAG_ID_MAP.get(normalized)
            if fallback:
                fallback_tag = Tag.browse(fallback).exists()
                if fallback_tag:
                    result.add(fallback_tag.id)

        return Tag, sorted(result)

    def _recompute_sale_line_and_inventory_tags(self, sale_lines):
        if not sale_lines:
            return

        field = sale_lines._fields.get('x_sale_line_tags')
        if not field or field.type != 'many2many':
            return

        for line in sale_lines.sudo():
            activity_types = line.activity_ids.mapped('type') if 'activity_ids' in line._fields else []
            Tag, tag_ids = self._resolve_tag_ids_for_types(activity_types)
            if not Tag:
                continue
            line.write({'x_sale_line_tags': [(6, 0, tag_ids)]})
            self._sync_inventory_tags_from_sale_line(line, tag_ids, Tag._name)

    def _sync_inventory_tags_from_sale_line(self, sale_line, tag_ids, tag_model):
        moves = self.env['stock.move']
        if 'move_ids' in sale_line._fields:
            moves |= sale_line.move_ids
        if not moves:
            return

        for field_name in ('x_tags_activities', 'x_activity_tags', 'x_sale_line_tags'):
            field = moves._fields.get(field_name)
            if not field or field.type != 'many2many' or field.comodel_name != tag_model:
                continue
            moves.sudo().write({field_name: [(6, 0, tag_ids)]})
            break

        pickings = moves.mapped('picking_id')
        for field_name in ('x_tags_activities', 'x_activity_tags', 'x_sale_line_tags'):
            field = pickings._fields.get(field_name)
            if not field or field.type != 'many2many' or field.comodel_name != tag_model:
                continue
            pickings.sudo().write({field_name: [(6, 0, tag_ids)]})
            break
