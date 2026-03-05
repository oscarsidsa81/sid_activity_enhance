from odoo import fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    sid_activity_tag_ids = fields.Many2many(
        comodel_name='sid.activity.tag',
        relation='sid_stock_move_activity_tag_rel',
        column1='move_id',
        column2='tag_id',
        string='Tags actividades',
        help='Tags derivados de actividades asociadas a la línea de venta.',
    )
