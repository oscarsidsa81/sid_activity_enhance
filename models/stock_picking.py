from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # Resumen (derivado) de tags de actividades presentes en los movimientos del albarán.
    # No se almacena para evitar duplicidad: la fuente operativa está en stock.move.
    sid_activity_tag_ids = fields.Many2many(
        comodel_name='sid.activity.tag',
        compute='_compute_sid_activity_tag_ids',
        string='Tags actividades',
        help='Resumen de tags derivados de actividades en los movimientos del albarán.',
        store=False,
    )

    @api.depends('move_lines.sid_activity_tag_ids')
    def _compute_sid_activity_tag_ids(self):
        for picking in self:
            tags = picking.move_lines.mapped('sid_activity_tag_ids')
            picking.sid_activity_tag_ids = tags
