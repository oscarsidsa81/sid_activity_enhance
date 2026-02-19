from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleLineActivityWizard(models.TransientModel):
    _name = 'sale.line.activity.wizard'
    _description = 'Batch assign activities to sale order lines'

    operation = fields.Selection([
        ('add', 'Add selected activities'),
        ('remove', 'Remove selected activities'),
    ], required=True, default='add')

    user_id = fields.Many2one('res.users', string='Responsible')
    date = fields.Date(string='Activity Date', default=fields.Date.context_today)
    description = fields.Char(string='Description')

    activity_type_ids = fields.Many2many(
        'sale.activity.tag.rule',
        string='Activity Types',
        help='Select activity types to add/remove in batch.'
    )

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        if self.env.context.get('active_model') != 'sale.order.line':
            return vals
        active_ids = self.env.context.get('active_ids', [])
        vals['description'] = _('Actividad creada en lote (%s líneas)') % len(active_ids)
        return vals

    def _selected_types(self):
        self.ensure_one()
        return self.activity_type_ids.mapped('activity_type')

    def action_apply(self):
        self.ensure_one()
        if self.env.context.get('active_model') != 'sale.order.line':
            raise UserError(_('This wizard can only be used from sale order lines.'))

        sale_lines = self.env['sale.order.line'].browse(self.env.context.get('active_ids', [])).exists()
        if not sale_lines:
            raise UserError(_('No sale order lines selected.'))

        selected_types = self._selected_types()
        if not selected_types:
            raise UserError(_('Select at least one activity type.'))

        Activity = self.env['sale.activity'].sudo()

        if self.operation == 'add':
            for line in sale_lines:
                for act_type in selected_types:
                    exists = Activity.search([
                        ('sale_line_id', '=', line.id),
                        ('type', '=', act_type),
                    ], limit=1)
                    if exists:
                        continue
                    Activity.create({
                        'sale_line_id': line.id,
                        'type': act_type,
                        'user_id': self.user_id.id or False,
                        'date': self.date,
                        'description': self.description or _('Actividad creada en lote'),
                    })
        else:
            acts = Activity.search([
                ('sale_line_id', 'in', sale_lines.ids),
                ('type', 'in', selected_types),
            ])
            acts.unlink()

        return {'type': 'ir.actions.act_window_close'}
