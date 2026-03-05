from odoo import fields, models


class SidActivityTag(models.Model):
    _name = 'sid.activity.tag'
    _description = 'SID Activity Tag'
    _order = 'sequence, name, id'

    name = fields.Char(required=True, index=True)
    code = fields.Char(index=True, help='Código estable para mapeos (ej. mecanizar, cortar, pintar).')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    color = fields.Integer()

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'El código de tag debe ser único.'),
        ('name_unique', 'unique(name)', 'El nombre de tag debe ser único.'),
    ]
