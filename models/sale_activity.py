from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleActivity(models.Model):
    _inherit = 'sale.activity'

    # --- Campos Studio migrados ---
    desc_sale_line = fields.Text(
        string='Descripción Venta',
        related='sale_line_id.name',
        readonly=True,
        store=False,
    )

    fecha_venta = fields.Datetime(
        string='Fecha Contractual Venta',
        related='sale_line_id.calculated_date',
        readonly=True,
        store=True,
    )

    item = fields.Char(
        string='Item',
        related='sale_line_id.item',
        readonly=True,
        store=True,
    )

    peso = fields.Float(
        string='Peso Unitario',
        related='product_id.weight',
        readonly=True,
        store=False,
    )

    qty = fields.Float(
        string='Cantidad Solicitada',
        related='sale_line_id.product_uom_qty',
        readonly=True,
        store=True,
    )

    peso_total = fields.Float(
        string='Peso Total',
        compute='_compute_peso_total',
        store=True,
        readonly=True,
    )

    @api.depends('qty', 'peso')
    def _compute_peso_total(self):
        for rec in self:
            rec.peso_total = (rec.peso or 0.0) * (rec.qty or 0.0)

    # --- Overrides / validaciones / sincronizaciones ---

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._check_duplicate_activity()
        records._check_route_vs_picking_type()
        records._sync_sale_line_tags()
        return records

    def write(self, vals):
        res = super().write(vals)
        # Si cambian campos relevantes, revalidar y/o resincronizar.
        relevant_dup = {'sale_line_id', 'type'}
        relevant_route = {'picking_type_id', 'sale_line_route'}
        relevant_tags = {'type', 'sale_line_id'}

        if relevant_dup.intersection(vals.keys()):
            self._check_duplicate_activity()
        if relevant_route.intersection(vals.keys()):
            self._check_route_vs_picking_type()
        if relevant_tags.intersection(vals.keys()):
            self._sync_sale_line_tags()
        return res

    def _check_duplicate_activity(self):
        """Evita duplicados por (sale_line_id, type).

        La server action original comprobaba solo sale_line_id; aquí lo hacemos más estricto
        y coherente con el mensaje mostrado al usuario.
        """
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
                ) % (dup.item or rec.item or '', rec.type))

    def _check_route_vs_picking_type(self):
        """Replica la acción 'OV - Revisar type':

        Si se informa un tipo de operación (picking_type_id), su route (sale_line_route)
        debe estar dentro de las rutas que contienen reglas para ese picking type.
        """
        Route = self.env['stock.location.route'].sudo()
        for rec in self.filtered(lambda r: r.picking_type_id and r.sale_line_route):
            allowed_routes = Route.search([('rule_ids.picking_type_id', '=', rec.picking_type_id.id)])
            if rec.sale_line_route not in allowed_routes:
                raise UserError(_("Ojo, indicar un tipo de operación acorde a la ruta"))

    # --- Sincronización de tags en sale.order.line ---

    def _sync_sale_line_tags(self):
        """Mantiene los tags de la línea de venta en función del tipo de actividad.

        Sustituye la base.automation 'OV - TAG sale.activities en líneas de venta' y
        varias server actions auxiliares.
        """
        # Si el campo no existe en este entorno, no hacemos nada.
        SOL = self.env['sale.order.line']
        if 'sale_line_tags' not in SOL._fields:
            return

        tag_model = SOL._fields['sale_line_tags'].comodel_name
        Tag = self.env[tag_model].sudo()

        # Fallback por ID (tal y como estaba en Studio). Si en otra BD cambian IDs,
        # intentamos resolver primero por nombre.
        id_map = {
            'cortar': 1,
            'mecanizar': 15,
            'roscar': 16,
            'biselar': 17,
            'ranurar': 18,
            'pintar': 19,
            'curvar': 20,
            'galvanizar': 21,
            'ensayos': 22,
            'montaje': 23,
            'inspeccion interna': 24,
            'inspeccion cliente': 25,
            'inspeccion': 26,
            'taller': 27,
            'colada': 29,
        }

        def _normalize(s):
            return (s or '').strip().lower()

        def _resolve_tag_id(activity_type):
            t = _normalize(activity_type)
            if not t:
                return False
            # 1) Preferir búsqueda por nombre (robusto a IDs).
            # Nota: usamos ilike para tolerar mayúsculas/acentos.
            tag = Tag.search([('name', '=ilike', t)], limit=1)
            if not tag:
                tag = Tag.search([('name', 'ilike', t.replace('inspeccion', 'inspección'))], limit=1)
            if tag:
                return tag.id
            # 2) Fallback por id.
            tid = id_map.get(t)
            if tid:
                return Tag.browse(tid).exists().id or False
            return False

        for rec in self.filtered(lambda r: r.sale_line_id):
            tid = _resolve_tag_id(rec.type)
            if not tid:
                continue
            # Añadir tag sin duplicar
            rec.sale_line_id.sudo().write({'sale_line_tags': [(4, tid, 0)]})
