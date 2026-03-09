from odoo import fields, models


class SidActivityTag(models.Model):
    _name = 'sid.activity.tag'
    _description = 'Activity Tag'
    _order = 'sequence, name, id'

    name = fields.Char(required=True, index=True)
    code = fields.Char(index=True, help='Código estable para mapeos (ej. mecanizar, cortar, pintar).')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    color = fields.Integer()
    stock_move_ids = fields.Many2many(
        'stock.move', 'sid_stock_move_activity_tag_rel', 'tag_id', 'move_id', string='Stock moves'
    )
    sale_line_ids = fields.Many2many(
        'sale.order.line', 'sid_sale_line_activity_tag_rel', 'tag_id', 'sale_line_id', string='Sale order lines'
    )

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'El código de tag debe ser único.'),
        ('name_unique', 'unique(name)', 'El nombre de tag debe ser único.'),
    ]
