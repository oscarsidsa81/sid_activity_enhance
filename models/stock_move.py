from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    sid_activity_tag_ids = fields.Many2many(
        comodel_name='sid.activity.tag',
        relation='sid_stock_move_activity_tag_rel',
        column1='stock_move_id',
        column2='tag_id',
        string='Tags actividades',
        help='Tags derivados de actividades asociadas a la línea de venta.',
    )

    activity_ids = fields.One2many(string='Activity ID', related='sale_line_id.activity_ids')
    todo = fields.Boolean(string='Todo', compute='_compute_todo', store=False)

    @api.depends('activity_ids.stage', 'activity_ids.picking_type_id', 'picking_id.picking_type_id')
    def _compute_todo(self):
        for rec in self:
            rec.todo = any(
                act.stage != 'done' and act.picking_type_id == rec.picking_id.picking_type_id
                for act in rec.activity_ids
            )
