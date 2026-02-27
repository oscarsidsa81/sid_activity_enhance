from odoo import api, SUPERUSER_ID


def _build_name_domain(explicit_names, keyword_names):
    name_domain = [('name', 'in', list(explicit_names))]
    for kw in keyword_names:
        name_domain = ['|', ('name', 'ilike', kw)] + name_domain
    return name_domain


def _build_domain(model, model_names, explicit_names, keyword_names):
    domain = [('model_id.model', 'in', model_names)]
    if 'active' in model._fields:
        domain.append(('active', '=', True))
    return domain + _build_name_domain(explicit_names, keyword_names)


def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})

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

    model_names = ['sale.activity', 'sale.order.line', 'stock.move', 'stock.picking']

    explicit_names = {
        'BISELAR',
        'CERTIFICADOS INVENTARIO',
        'CORTAR',
        'GALVANIZADO',
        'MECANIZADO',
        'ROSCAR',
        'OV - Añade Activity Cortar',
        'OV - Añade Activity Galvanizado',
        'OV - Añade Activity Mecanizado',
        'OV - Añade tag BISELAR',
        'OV - Añade tag CERTIFICADOS',
        'OV - Añade tag CORTAR',
        'OV - Añade tag GALVANIZADO',
        'OV - Añade tag MECANIZAR',
        'OV - Añade tag ROSCAR',
        'OV - TAG sale.activities borrar en líneas de venta',
        'OV - TAG sale.activities en líneas de venta',
        'OV - Actividades a línea albarán',
        'OV - Actividades',
        'OV - Actividades duplicadas',
        'OV - Revisar type',
    }

    keyword_names = [
        'tag sale.activities', 'añade activity', 'añade tag',
        'cortar', 'mecaniz', 'galvan', 'bisel', 'roscar',
        'certificados', 'actividades hereda', 'actividades a linea albaran',
    ]

    autos = env['base.automation'].sudo().search(
        _build_domain(env['base.automation'], model_names, explicit_names, keyword_names)
    )
    if autos:
        autos.write({'active': False})

    acts = env['ir.actions.server'].sudo().search(
        _build_domain(env['ir.actions.server'], model_names, explicit_names, keyword_names)
    )
    if acts and 'active' in acts._fields:
        acts.write({'active': False})
