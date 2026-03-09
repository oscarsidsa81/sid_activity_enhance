import logging
from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

TAG_DATA = [
    ('mecanizar', 'MECANIZAR', 10, 1),
    ('cortar', 'CORTAR', 20, 2),
    ('roscar', 'ROSCAR', 30, 3),
    ('biselar', 'BISELAR', 40, 4),
    ('ranurar', 'RANURAR', 50, 5),
    ('pintar', '3LPE / PINTAR', 60, 6),
    ('curvar', 'CURVAR', 70, 7),
    ('galvanizar', 'GALVANIZAR', 80, 8),
    ('ensayos', 'ENSAYOS', 90, 9),
    ('montaje', 'MONTAJE', 100, 10),
    ('inspeccion interna', 'INSPECCION INTERNA', 110, 11),
    ('inspeccion cliente', 'INSPECCION CLIENTE', 120, 12),
    ('inspeccion', 'INSPECCION', 130, 13),
    ('taller', 'TALLER', 140, 14),
]


def _ensure_tags_and_rules(env):
    Tag = env['sid.activity.tag'].sudo()
    Rule = env['sale.activity.tag.rule'].sudo()
    for code, name, sequence, color in TAG_DATA:
        tag = Tag.search([('code', '=', code)], limit=1)
        values = {'code': code, 'name': name, 'sequence': sequence, 'color': color, 'active': True}
        if not tag:
            tag = Tag.create(values)
        else:
            tag.write(values)
        rule = Rule.search([('activity_type', '=', code)], limit=1)
        if not rule:
            Rule.create({'activity_type': code, 'sid_tag_id': tag.id, 'active': True})
        elif rule.sid_tag_id != tag:
            rule.write({'sid_tag_id': tag.id, 'active': True})


def _backfill_picking_type(env):
    Activity = env['sale.activity'].sudo()
    acts = Activity.search([('sale_line_route', '!=', False), ('picking_type_id', '=', False)])
    fixed = 0
    for act in acts:
        picking_type = act._get_route_certificate_picking_type()
        if picking_type:
            act.write({'picking_type_id': picking_type.id})
            fixed += 1
    return fixed


def _recompute_from_activities(env):
    Activity = env['sale.activity'].sudo()
    activities = Activity.search([('sale_line_id', '!=', False)])
    sale_lines = activities.mapped('sale_line_id').exists()
    if sale_lines:
        activities._recompute_sale_line_and_inventory_tags(sale_lines)
    return len(sale_lines)


def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _logger.info('[sid_activity_enhance] post-init start')
    _ensure_tags_and_rules(env)
    fixed = _backfill_picking_type(env)
    recomputed = _recompute_from_activities(env)
    _logger.info(
        '[sid_activity_enhance] post-init done | picking_fixed=%s recomputed_sale_lines=%s',
        fixed,
        recomputed,
    )
