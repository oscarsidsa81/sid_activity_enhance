import logging
_logger = logging.getLogger(__name__)

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

    stats = {
        'rules_total': 0,
        'rules_migrated': 0,
        'sol_found': 0,
        'sol_updated': 0,
        'moves_found': 0,
        'moves_updated': 0,
        'legacy_links_total': 0,
        'legacy_links_mapped': 0,
        'legacy_links_unmapped': 0,
        'unmapped_names': set(),
    }

    _logger.info('[sid_activity_enhance] MIGRATION start (legacy x_ -> sid)')

    def _model_exists(name):
        try:
            env[name]
            return True
        except KeyError:
            return False

    def _map_legacy_tags(legacy_rs, legacy_to_sid):
        cmds = []
        for lt in legacy_rs:
            stats['legacy_links_total'] += 1
            lname = (getattr(lt, 'display_name', False) or getattr(lt, 'name', False) or '').strip()
            sid_id = legacy_to_sid.get(lname)
            if sid_id:
                stats['legacy_links_mapped'] += 1
                cmds.append(sid_id)
            else:
                stats['legacy_links_unmapped'] += 1
                if lname:
                    stats['unmapped_names'].add(lname)
        return list(dict.fromkeys(cmds))  # unique preserve order


    # ---------------------------------------------------------------------
    # 1) Ensure sequence exists
    # ---------------------------------------------------------------------
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

    # ---------------------------------------------------------------------
    # 2) Disable / remove legacy UI automations & server actions
    #    (they used to write to `display_name` and to manage tags with hard IDs)
    # ---------------------------------------------------------------------
    model_names = ['sale.activity', 'sale.order.line', 'stock.move', 'stock.picking']

    explicit_names = {
        'OV - Actividades',
        'OV - Actividades duplicadas',
        'OV - Revisar type',
        'OV - TAG sale.activities en líneas de venta',
        'OV - TAG sale.activities borrar en líneas de venta',
    }

    keyword_names = [
        'tag sale.activities',
        'ov - actividades',
        'actividades duplicadas',
        'revisar type',
        'display_name',
    ]

    autos = env['base.automation'].sudo().search(
        _build_domain(env['base.automation'], model_names, explicit_names, keyword_names)
    )
    if autos:
        autos.write({'active': False})

    acts = env['ir.actions.server'].sudo().search(
        _build_domain(env['ir.actions.server'], model_names, explicit_names, keyword_names)
    )
    if acts:
        if 'active' in acts._fields:
            acts.write({'active': False})
        else:
            # Some Odoo.sh builds do not have `active` on ir.actions.server:
            # we unlink only the matching legacy actions (safe - they are UI exports).
            acts.unlink()

    # ---------------------------------------------------------------------
    # 3) Ensure stable tags + rules exist (no Studio dependency)
    # ---------------------------------------------------------------------
    Rule = env['sale.activity.tag.rule'].sudo()
    Tag = env['sid.activity.tag'].sudo()
    activity_type_field = env['sale.activity']._fields.get('type')
    selection = list(getattr(activity_type_field, 'selection', []) or [])

    # normalized activity_type -> (tag_code, tag_name)
    type_to_tag = {
        'mecanizar': ('mecanizar', 'MECANIZAR'),
        'cortar': ('cortar', 'CORTAR'),
        'roscar': ('roscar', 'ROSCAR'),
        'biselar': ('biselar', 'BISELAR'),
        'ranurar': ('ranurar', 'RANURAR'),
        'pintar': ('pintar', '3LPE / PINTAR'),
        'curvar': ('curvar', 'CURVAR'),
        'galvanizar': ('galvanizar', 'GALVANIZAR'),
        'ensayos': ('ensayos', 'ENSAYOS'),
        'montaje': ('montaje', 'MONTAJE'),
        'inspeccion interna': ('inspeccion interna', 'INSPECCION INTERNA'),
        'inspeccion cliente': ('inspeccion cliente', 'INSPECCION CLIENTE'),
        'inspeccion': ('inspeccion', 'INSPECCION'),
        'taller': ('taller', 'TALLER'),
    }

    # helper normalization (keep same logic as in model)
    def norm(raw):
        value = (raw or '').strip().lower()
        return value.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')

    # 3.1) Ensure tag master data exists
    for key, _label in selection:
        normalized = norm(key)
        info = type_to_tag.get(normalized)
        if not info:
            continue
        code, name = info
        if not Tag.search([('code', '=', code)], limit=1):
            Tag.create({'code': code, 'name': name, 'sequence': 10, 'active': True})

    # 3.2) Ensure default rules exist (one per type)
    for key, _label in selection:
        normalized = norm(key)
        info = type_to_tag.get(normalized)
        if not info:
            continue
        code, _name = info
        if Rule.search_count([('activity_type', '=', key)]) > 0:
            continue
        tag = Tag.search([('code', '=', code)], limit=1)
        if tag:
            # Campo operativo estable
            Rule.create({'activity_type': key, 'sid_tag_id': tag.id, 'active': True})

    # -----------------------------------------------------------------
    # 3.3) Backfill picking_type_id en actividades existentes
    # -----------------------------------------------------------------
    # Si la ruta contempla un picking marcado como is_certificate_type, debe rellenarse.
    # Esto corrige el caso "Madrid - Stock" donde antes quedaba en blanco.
    try:
        SA = env['sale.activity'].sudo()
        if 'sale_line_route' in SA._fields and 'picking_type_id' in SA._fields:
            missing = SA.search([('sale_line_route', '!=', False), ('picking_type_id', '=', False)])
            if missing:
                _logger.info('[sid_activity_enhance] Backfill picking_type_id: %s sale.activity a revisar', len(missing))
                missing._autofill_picking_type_from_route()
    except Exception as e:
        _logger.warning('[sid_activity_enhance] Backfill picking_type_id skipped: %s', e)

    # -----------------------------------------------------------------
    # 4) One-time migration from legacy Studio fields to sid_* fields
    # -----------------------------------------------------------------
    # --------------------------------------------------------------
    # Legacy migration (if Studio model exists)
    # --------------------------------------------------------------
    legacy_map = {}
    if 'x_stock.move.tags' in env:
        LegacyTag = env['x_stock.move.tags'].sudo()
        # map by display_name/name -> new sid.activity.tag
        for lt in LegacyTag.search([]):
            key = (lt.display_name or lt.name or '').strip().upper()
            if not key:
                continue
            st = Tag.search([('name', '=ilike', key)], limit=1)
            if st:
                legacy_map[lt.id] = st.id


    # ---------------------------------------------------------------------
    # sale.activity.tag.rule: migrate legacy integer tag_id (x_stock.move.tags id) -> sid_tag_id
    # ---------------------------------------------------------------------
    Rule = env['sale.activity.tag.rule'].sudo()
    if legacy_map and 'sid_tag_id' in Rule._fields:
        rules = Rule.search([('sid_tag_id', '=', False), ('tag_id', '!=', False)])
        stats['rules_total'] = len(rules)
        for r in rules:
            sid_id = legacy_map.get(r.tag_id)
            if sid_id:
                r.write({'sid_tag_id': sid_id, 'tag_id': False})
                stats['rules_migrated'] += 1
            else:
                # try by name if we can read legacy tag
                try:
                    lt = env['x_stock.move.tags'].sudo().browse(r.tag_id).exists()
                    lname = (lt.display_name or lt.name or '').strip()
                except Exception:
                    lname = ''
                if lname:
                    stats['unmapped_names'].add(lname)
    # sale.order.line: x_sale_line_tags -> sid_activity_tag_ids (translated)
    SOL = env['sale.order.line'].sudo()
    if legacy_map and 'sid_activity_tag_ids' in SOL._fields and 'x_sale_line_tags' in SOL._fields:
        lines = SOL.search([('x_sale_line_tags', '!=', False)])
        stats['sol_found'] = len(lines)
        for line in lines:
            stats['legacy_links_total'] += len(line.x_sale_line_tags.ids)
            new_ids = [legacy_map.get(tid) for tid in line.x_sale_line_tags.ids]
            stats['legacy_links_mapped'] += len([x for x in new_ids if x])
            stats['legacy_links_unmapped'] += len([x for x in new_ids if not x])
            new_ids = [x for x in new_ids if x]
            if new_ids:
                line.write({'sid_activity_tag_ids': [(6, 0, sorted(set(new_ids)))]})
                stats['sol_updated'] += 1

    # stock.move: x_tags_activities/x_activity_tags -> sid_activity_tag_ids (translated)
    Move = env['stock.move'].sudo()
    if legacy_map and 'sid_activity_tag_ids' in Move._fields:
        legacy_fields = [f for f in ('x_tags_activities', 'x_activity_tags', 'x_sale_line_tags') if f in Move._fields]
        if legacy_fields:
            for lf in legacy_fields:
                moves = Move.search([(lf, '!=', False)])
                if not moves:
                    continue
                for mv in moves:
                    old_ids = getattr(mv, lf).ids
                    new_ids = [legacy_map.get(tid) for tid in old_ids]
                    new_ids = [x for x in new_ids if x]
                    if new_ids:
                        mv.write({'sid_activity_tag_ids': [(6, 0, sorted(set(new_ids)))]})
                stats['moves_updated'] += 1
                break


    # ---------------------------------------------------------------------
    # MIGRATION LOG SUMMARY
    # ---------------------------------------------------------------------
    unmapped = ", ".join(sorted(stats['unmapped_names'])) if stats['unmapped_names'] else "-"
    _logger.info(
        "[sid_activity_enhance] MIGRATION done | rules=%s migrated=%s | SOL found=%s updated=%s | MOVES found=%s updated=%s | "
        "legacy_links total=%s mapped=%s unmapped=%s | unmapped_names=%s",
        stats['rules_total'], stats['rules_migrated'],
        stats['sol_found'], stats['sol_updated'],
        stats['moves_found'], stats['moves_updated'],
        stats['legacy_links_total'], stats['legacy_links_mapped'], stats['legacy_links_unmapped'],
        unmapped,
    )
