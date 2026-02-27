"""
Run inside `odoo shell -d <db>` with:

exec(open('scripts/odoo_shell_sid_check.py').read())

Set `AUTO_UPGRADE = True` only when you want this script to trigger module upgrade.
"""

AUTO_UPGRADE = False
MODULE = 'sid_activity_enhance'
EXPECTED_VERSION = '15.0.1.0.1'

XMLIDS = [
    f'{MODULE}.sid_view_sale_line_activity_wizard_form',
    f'{MODULE}.sid_action_sale_line_activity_wizard',
    f'{MODULE}.sid_view_sale_order_line_tree_wizard_button',
    f'{MODULE}.sid_view_sale_order_form_wizard_button',
    f'{MODULE}.sid_view_sale_activity_tag_rule_tree',
    f'{MODULE}.sid_view_sale_activity_tag_rule_form',
    f'{MODULE}.sid_action_sale_activity_tag_rule',
    f'{MODULE}.sid_menu_sale_activity_tag_rule',
]


def hr(title):
    print("\n" + "=" * 110)
    print(title)
    print("=" * 110)


def ref(xid):
    return env.ref(xid, raise_if_not_found=False)


def print_state():
    hr("0) ESTADO DE MODULOS")
    mods = env['ir.module.module'].sudo().search([('name', 'in', [
        'sid_activity_enhance', 'oct_so_line_info', 'oct_certificate_receptions'
    ])], order='name')
    for m in mods:
        print(f"- {m.name:30} state={m.state:12} version={m.installed_version or m.latest_version}")

    sid = mods.filtered(lambda m: m.name == MODULE)[:1]
    if sid:
        installed = sid.installed_version or ''
        if EXPECTED_VERSION and installed and installed != EXPECTED_VERSION:
            print(f"! Version mismatch: installed={installed} expected={EXPECTED_VERSION}")


def run_upgrade_if_needed():
    mod = env['ir.module.module'].sudo().search([('name', '=', MODULE)], limit=1)
    if not mod:
        print(f"Module {MODULE} not found")
        return
    if AUTO_UPGRADE:
        hr("UPGRADE")
        print(f"Running immediate upgrade for {MODULE}...")
        mod.button_immediate_upgrade()
        env.cr.commit()
        print("Upgrade done.")
    else:
        print("AUTO_UPGRADE=False -> read-only mode (no upgrade executed).")


def check_xmlids():
    hr("1) XMLIDs CLAVE")
    missing = []
    for xid in XMLIDS:
        rec = ref(xid)
        if rec:
            print(f"OK      {xid:70} -> {rec._name}:{rec.id}")
        else:
            print(f"MISSING {xid}")
            missing.append(xid)
    return missing


def check_models_acl_arch():
    hr("2) MODELOS NUEVOS")
    for model_name in ['sale.activity.tag.rule', 'sale.line.activity.wizard']:
        m = env['ir.model'].sudo().search([('model', '=', model_name)], limit=1)
        print(f"- {model_name:30} exists={bool(m)} id={m.id if m else None}")

    hr("3) ACL")
    wizard_acl = env['ir.model.access'].sudo().search([('model_id.model', '=', 'sale.line.activity.wizard')])
    rule_acl = env['ir.model.access'].sudo().search([('model_id.model', '=', 'sale.activity.tag.rule')])
    print("ACL wizard count:", len(wizard_acl))
    for a in wizard_acl:
        print(f" - {a.id} {a.name} group={a.group_id.display_name if a.group_id else 'ALL'}")
    print("ACL tag.rule count:", len(rule_acl))
    for a in rule_acl:
        print(f" - {a.id} {a.name} group={a.group_id.display_name if a.group_id else 'ALL'}")

    hr("4) ARCH COMPILADO")
    tree_arch = env['sale.order.line'].fields_view_get(view_type='tree').get('arch', '')
    form_arch = env['sale.order'].fields_view_get(view_type='form').get('arch', '')
    print("sale.order.line tree contiene botón:", 'sid - Batch Activities' in tree_arch)
    print("sale.order form contiene botón:", 'sid - Batch Activities' in form_arch)


print_state()
run_upgrade_if_needed()
print_state()
missing = check_xmlids()
check_models_acl_arch()

hr("RESUMEN")
if missing:
    print("Aún faltan XMLIDs:")
    for xid in missing:
        print(" -", xid)
else:
    print("OK: todos los XMLIDs clave existen.")

if missing:
    print("\nSiguiente paso recomendado:")
    print("  mod = env['ir.module.module'].sudo().search([('name','=','sid_activity_enhance')], limit=1)")
    print("  mod.button_immediate_upgrade()")
