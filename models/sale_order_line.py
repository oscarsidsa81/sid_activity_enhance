from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    sid_activity_tag_ids = fields.Many2many(
        comodel_name='sid.activity.tag',
        relation='sid_sale_line_activity_tag_rel',
        column1='sale_line_id',
        column2='tag_id_legacy',
        string='Tags actividades',
        help='Tags derivados de los tipos de actividades vinculadas a la línea.',
    )

    def action_open_sid_batch_activities(self):
        action = self.env.ref('sid_activity_enhance.sid_action_sale_line_activity_wizard', raise_if_not_found=False)
        result = action.read()[0] if action else {
            'type': 'ir.actions.act_window',
            'name': 'Asignar Actividades',
            'res_model': 'sale.line.activity.wizard',
            'view_mode': 'form',
            'target': 'new',
        }
        result['context'] = {'active_model': 'sale.order.line', 'active_ids': self.ids}
        return result

    def init(self):
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS idx_sid_sale_line_activity_tag_rel_line
            ON sid_sale_line_activity_tag_rel (sale_line_id)
        """)
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS idx_sid_sale_line_activity_tag_rel_tag
            ON sid_sale_line_activity_tag_rel (tag_id_legacy)
        """)
