from odoo import api, SUPERUSER_ID


def post_init_hook(cr, registry):
    """Asegura elementos de configuración y desactiva automatizaciones redundantes.

    Este módulo mueve lógicas desde Server Actions / Automations a Python.
    Para evitar dobles ejecuciones, desactivamos las automatizaciones conocidas.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})

    # 1) Asegurar secuencia usada para display_name.
    seq = env['ir.sequence'].sudo().search([('code', '=', 'sale.activity')], limit=1)
    if not seq:
        env['ir.sequence'].sudo().create({
            'name': 'Sale Activity',
            'code': 'sale.activity',
            'implementation': 'no_gap',
            'prefix': 'ACT/',
            'padding': 5,
            'company_id': False,
        })

    # 2) Desactivar automations/server actions antiguos si existen (evitar doble lógica).
    # Nota: no usamos xml_id porque en tu DB venían como __export__.
    automation_names = {
        'OV - TAG sale.activities en líneas de venta',
    }
    autos = env['base.automation'].sudo().search([
        ('model_id.model', '=', 'sale.activity'),
        ('name', 'in', list(automation_names)),
        ('active', '=', True),
    ])
    if autos:
        autos.write({'active': False})

    action_names = {
        'OV - Actividades',
        'OV - Actividades duplicadas',
        'OV - Revisar type',
        'OV - TAG sale.activities en líneas de venta',
    }
    acts = env['ir.actions.server'].sudo().search([
        ('model_id.model', '=', 'sale.activity'),
        ('name', 'in', list(action_names)),
        ('active', '=', True),
    ])
    if acts:
        acts.write({'active': False})
