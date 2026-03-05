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
        'sid.activity.tag',
        string='Activity Types',
        help='Select activity types to add/remove in batch.'
    )

    line_ids = fields.Many2many('sale.order.line', string='Sale Lines', readonly=True)
    preview_activity_ids = fields.Many2many(
        'sale.activity',
        string='Activities in selected lines',
        compute='_compute_existing_activities',
        readonly=True,
        store=False,
    )
    # Legacy compatibility: some clients/views may still post this field name.
    existing_activity_ids = fields.Many2many(
        'sale.activity',
        string='Existing Activities (legacy)',
        compute='_compute_existing_activities',
        readonly=True,
        store=False,
    )

    @api.depends('line_ids')
    @api.depends_context('active_ids', 'active_model')
    def _compute_existing_activities(self):
        for wiz in self:
            lines = wiz.line_ids
            if not lines and wiz.env.context.get('active_model') == 'sale.order.line':
                active_ids = wiz.env.context.get('active_ids', [])
                lines = wiz.env['sale.order.line'].browse(active_ids).exists()
            acts = wiz.env['sale.activity'].sudo().search([('sale_line_id', 'in', lines.ids)])
            wiz.preview_activity_ids = [(6, 0, acts.ids)]
            wiz.existing_activity_ids = [(6, 0, acts.ids)]


    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        if self.env.context.get('active_model') != 'sale.order.line':
            return vals
        active_ids = self.env.context.get('active_ids', [])
        if active_ids:
            vals['line_ids'] = [(6, 0, active_ids)]
        # Default instructions requested for the operator.
        vals['description'] = _('Revisar instrucciones en campo Comments de la linea de venta')
        return vals

    def _selected_types(self):
        self.ensure_one()
        # sid.activity.tag.code matches exactly the key of sale.activity.type selection
        return self.activity_type_ids.mapped('code')

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
            existing = Activity.search([
                ('sale_line_id', 'in', sale_lines.ids),
                ('type', 'in', selected_types),
            ])
            duplicated_pairs = {(act.sale_line_id.id, act.type) for act in existing}
            if duplicated_pairs:
                details = []
                for line in sale_lines:
                    for act_type in selected_types:
                        if (line.id, act_type) in duplicated_pairs:
                            details.append(_('- Línea %s ya tiene actividad tipo "%s"') % (
                                line.display_name, act_type,
                            ))
                if details:
                    raise UserError(_(
                        'Ya existen actividades del mismo tipo en algunas líneas seleccionadas.\n\n%s\n\n'
                        'Usa la operación "Remove selected activities" si deseas reemplazarlas.'
                    ) % ('\n'.join(details[:30])))

            for line in sale_lines:
                for act_type in selected_types:
                    Activity.create({
                        'sale_line_id': line.id,
                        'type': act_type,
                        'user_id': self.user_id.id or False,
                        'date': self.date,
                        'description': self.description or _('Revisar instrucciones en campo Comments de la linea de venta'),
                    })
        else:
            acts = Activity.search([
                ('sale_line_id', 'in', sale_lines.ids),
                ('type', 'in', selected_types),
            ])
            acts.unlink()

        return {'type': 'ir.actions.act_window_close'}
