from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    sid_activity_tag_ids = fields.Many2many(
        comodel_name='sid.activity.tag',
        relation='sid_stock_move_activity_tag_rel',
        column1='move_id',
        column2='legacy_tag_id',
        string='Tags actividades',
        help='Tags derivados de actividades asociadas a la línea de venta.',
    )

    has_activity_tags = fields.Boolean(string='Has activity tags', compute='_compute_has_activity_tags', store=True, index=True)

    @api.depends('sid_activity_tag_ids')
    def _compute_has_activity_tags(self):
        for rec in self:
            rec.has_activity_tags = bool(rec.sid_activity_tag_ids)

    def init(self):
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS idx_sid_stock_move_activity_tag_rel_move
            ON sid_stock_move_activity_tag_rel (move_id)
        """)
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS idx_sid_stock_move_activity_tag_rel_tag
            ON sid_stock_move_activity_tag_rel (tag_id_legacy)
        """)
