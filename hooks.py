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
            Rule.create({'activity_type': key, 'tag_id': tag.id, 'active': True})

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

    # sale.order.line: x_sale_line_tags -> sid_activity_tag_ids (translated)
    SOL = env['sale.order.line'].sudo()
    if legacy_map and 'sid_activity_tag_ids' in SOL._fields and 'x_sale_line_tags' in SOL._fields:
        lines = SOL.search([('x_sale_line_tags', '!=', False)])
        for line in lines:
            new_ids = [legacy_map.get(tid) for tid in line.x_sale_line_tags.ids]
            new_ids = [x for x in new_ids if x]
            if new_ids:
                line.write({'sid_activity_tag_ids': [(6, 0, sorted(set(new_ids)))]})

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
                break
