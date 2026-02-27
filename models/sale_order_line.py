from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # Compatibility field: some legacy related fields point to
    # `sale_line_id.calculated_date` (e.g. sale.activity.fecha_venta).
    # Keep it optional/read-only to avoid module upgrade crashes when the
    # original customization that provided this field is absent.
    calculated_date = fields.Datetime(string='Calculated Date', readonly=True)

    def action_open_sid_batch_activities(self):
        self.ensure_one()
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
