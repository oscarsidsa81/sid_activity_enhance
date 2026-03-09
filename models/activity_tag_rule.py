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
    legacy_tag_name = fields.Char(string='Legacy tag name')
    sid_tag_id = fields.Many2one('sid.activity.tag', string='Tag', ondelete='restrict', index=True, required=True)

    @api.onchange('sid_tag_id')
    def _onchange_sid_tag_id(self):
        for r in self:
            if r.sid_tag_id and not r.legacy_tag_name:
                r.legacy_tag_name = r.sid_tag_id.name

    _sql_constraints = [
        ('activity_type_unique', 'unique(activity_type)', 'Only one tag rule per activity type is allowed.'),
    ]
# TODO revisar para qué vale esto