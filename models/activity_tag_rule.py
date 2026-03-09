from odoo import fields, models


class SaleActivityTagRule(models.Model):
    _name = 'sale.activity.tag.rule'
    _description = 'Sale Activity Tag Rule'
    _order = 'activity_type'

    def _selection_activity_type(self):
        field = self.env['sale.activity']._fields.get('type')
        return list(getattr(field, 'selection', []) or [])

    active = fields.Boolean(default=True)
    activity_type = fields.Selection(selection='_selection_activity_type', required=True, index=True)
    sid_tag_id = fields.Many2one('sid.activity.tag', string='Tag', ondelete='restrict', index=True, required=True)

    _sql_constraints = [
        ('activity_type_unique', 'unique(activity_type)', 'Only one tag rule per activity type is allowed.'),
    ]
