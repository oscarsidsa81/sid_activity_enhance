from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # Tags de actividades (NO Studio). Se sincroniza desde sale.activity.
    # Modelo de tags estable del módulo (sid.activity.tag). Los modelos x_
    # sólo se consideran legacy/migración.
    sid_activity_tag_ids = fields.Many2many(
        comodel_name='sid.activity.tag',
        relation='sid_sale_line_activity_tag_rel',
        column1='sale_line_id',
        column2='tag_id',
        string='Tags actividades',
        help='Tags derivados de los tipos de actividades vinculadas a la línea.',
    )

    def action_open_sid_batch_activities(self):
        action = self.env.ref(
            'sid_activity_enhance.sid_action_sale_line_activity_wizard',
            raise_if_not_found=False,
        )
        if action:
            result = action.read()[0]
        else:
            result = {
                'type': 'ir.actions.act_window',
                'name': 'sid - Batch Activities',
                'res_model': 'sale.line.activity.wizard',
                'view_mode': 'form',
                'target': 'new',
            }
        result['context'] = {
            'active_model': 'sale.order.line',
            'active_ids': self.ids,
        }
        return result
