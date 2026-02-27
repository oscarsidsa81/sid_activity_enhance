from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

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
            'active_ids': self.order_line.ids,
        }
        return result
