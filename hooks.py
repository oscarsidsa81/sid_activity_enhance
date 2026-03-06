import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


TAG_DATA = [
    ('mecanizar', 'MECANIZAR'),
    ('cortar', 'CORTAR'),
    ('roscar', 'ROSCAR'),
    ('biselar', 'BISELAR'),
    ('ranurar', 'RANURAR'),
    ('pintar', '3LPE / PINTAR'),
    ('curvar', 'CURVAR'),
    ('galvanizar', 'GALVANIZAR'),
    ('ensayos', 'ENSAYOS'),
    ('montaje', 'MONTAJE'),
    ('inspeccion interna', 'INSPECCION INTERNA'),
    ('inspeccion cliente', 'INSPECCION CLIENTE'),
    ('inspeccion', 'INSPECCION'),
    ('taller', 'TALLER'),
]


def _ensure_tags_and_rules(env):
    Tag = env['sid.activity.tag'].sudo()
    Rule = env['sale.activity.tag.rule'].sudo()
    for sequence, (code, name) in enumerate(TAG_DATA, start=1):
        tag = Tag.search([('code', '=', code)], limit=1)
        if not tag:
            tag = Tag.create({'code': code, 'name': name, 'sequence': sequence})
        rule = Rule.search([('activity_type', '=', code)], limit=1)
        if not rule:
            Rule.create({'activity_type': code, 'sid_tag_id': tag.id, 'legacy_tag_name': name, 'active': True})
        elif not rule.sid_tag_id:
            rule.write({'sid_tag_id': tag.id})


def _backfill_picking_type(env):
    Activity = env['sale.activity'].sudo()
    acts = Activity.search([('sale_line_route', '!=', False), ('picking_type_id', '=', False)])
    fixed = 0
    for act in acts:
        route = act.sale_line_route
        rules = route.rule_ids.sorted(lambda r: (r.sequence, r.id)).filtered(
            lambda r: r.picking_type_id and getattr(r.picking_type_id, 'is_certificate_type', False)
        )
        if rules:
            act.write({'picking_type_id': rules[0].picking_type_id.id})
            fixed += 1
    return fixed


def _migrate_legacy_tags(env):
    stats = {'sol_updated': 0, 'move_updated': 0, 'unmapped': set()}
    if 'x_stock.move.tags' not in env:
        return stats
    Legacy = env['x_stock.move.tags'].sudo()
    Tag = env['sid.activity.tag'].sudo()
    tag_map = {}
    for legacy in Legacy.search([]):
        name = (legacy.display_name or legacy.name or '').strip()
        if not name:
            continue
        new = Tag.search([('name', '=ilike', name)], limit=1)
        if new:
            tag_map[legacy.id] = new.id
        else:
            stats['unmapped'].add(name)

    SOL = env['sale.order.line'].sudo()
    if 'x_sale_line_tags' in SOL._fields and 'sid_activity_tag_ids' in SOL._fields:
        for line in SOL.search([('x_sale_line_tags', '!=', False)]):
            ids = [tag_map.get(tid) for tid in line.x_sale_line_tags.ids]
            ids = sorted(set([i for i in ids if i]))
            if ids:
                line.write({'sid_activity_tag_ids': [(6, 0, ids)]})
                stats['sol_updated'] += 1

    Move = env['stock.move'].sudo()
    if 'sid_activity_tag_ids' in Move._fields:
        legacy_fields = [f for f in ('x_tags_activities', 'x_activity_tags', 'x_sale_line_tags') if f in Move._fields]
        for f in legacy_fields:
            for mv in Move.search([(f, '!=', False)]):
                ids = [tag_map.get(tid) for tid in mv[f].ids]
                ids = sorted(set([i for i in ids if i]))
                if ids:
                    mv.write({'sid_activity_tag_ids': [(6, 0, ids)]})
                    stats['move_updated'] += 1
            if legacy_fields:
                break
    return stats


def _recompute_from_activities(env):
    Activity = env['sale.activity'].sudo()
    lines = Activity.search([('sale_line_id', '!=', False)]).mapped('sale_line_id')
    if lines:
        lines.mapped('activity_ids')._recompute_sale_line_and_inventory_tags(lines)


def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _logger.info('[sid_activity_enhance] REBASE migration start')
    _ensure_tags_and_rules(env)
    legacy_stats = _migrate_legacy_tags(env)
    fixed = _backfill_picking_type(env)
    _recompute_from_activities(env)
    _logger.info(
        '[sid_activity_enhance] REBASE migration done | sol_updated=%s move_updated=%s picking_fixed=%s unmapped=%s',
        legacy_stats['sol_updated'],
        legacy_stats['move_updated'],
        fixed,
        ', '.join(sorted(legacy_stats['unmapped'])) or '-',
    )
