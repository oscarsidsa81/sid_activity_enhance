from odoo import _, exceptions, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        for picking in self:
            for move in picking.move_ids_without_package:
                if move.todo and (move.quantity_done > 0):
                    raise exceptions.ValidationError(_('Se debe realizar una actividad para %s') % move.product_id.display_name)
        return super().button_validate()
