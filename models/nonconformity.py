from odoo import fields, models


class SidNonconformity(models.Model):
    _inherit = 'sid.nonconformity'

    is_overdue = fields.Boolean(compute_sudo=True)
    days_open = fields.Integer(compute_sudo=True)
    days_to_close = fields.Integer(compute_sudo=True)
