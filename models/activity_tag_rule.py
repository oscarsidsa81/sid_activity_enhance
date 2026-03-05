from odoo import api, fields, models


class SaleActivityTagRule(models.Model):
    _name = 'sale.activity.tag.rule'
    _description = 'Sale Activity Tag Rule'
    _order = 'activity_type'

    def _selection_activity_type(self):
        field = self.env['sale.activity']._fields.get('type')
        return list(getattr(field, 'selection', []) or [])

    active = fields.Boolean(default=True)
    activity_type = fields.Selection(selection='_selection_activity_type', required=True, index=True)

    # Legacy column: in bases antiguas puede venir apuntando a x_stock.move.tags (IDs numéricos).
    # Lo dejamos como Integer para NO imponer FKs y poder migrar sin romper upgrades.
    tag_id = fields.Integer(string='Legacy tag id (x_)')

    # Campo operativo estable (no depende de Studio)
    sid_tag_id = fields.Many2one('sid.activity.tag', string='Tag', ondelete='restrict', index=True)

    @api.onchange('sid_tag_id')
    def _onchange_sid_tag_id(self):
        # Si el usuario fija el tag nuevo, limpiamos el legacy para evitar confusiones
        for r in self:
            if r.sid_tag_id:
                r.tag_id = False

    _sql_constraints = [
        ('activity_type_unique', 'unique(activity_type)', 'Only one tag rule per activity type is allowed.'),
    ]
