# Análisis del módulo `sid_activity_enhance`

## Decisiones funcionales confirmadas

1. **Fuente de verdad de tags**: `sale.order.line.activity_ids.type`.
2. **Automatizaciones legacy de tags/activities**: se desactivan temporalmente en transición.
3. **Tabla de mapeo**: v1 mínima `activity_type` + `tag_id` (sin `route_id`, sin `picking_type_id` override, sin `company_id`).
4. **UI**: menú técnico para administración de reglas.
5. **Certificados**: selección de `picking_type_id` por ruta, priorizando `is_certificate_type=True`.

## Compatibilidad temporal (legacy)

Durante transición, pueden coexistir automatizaciones antiguas en BD. El módulo debe:

- centralizar la lógica final,
- desactivar acciones legacy conocidas por nombre/keyword,
- y permitir retirada progresiva sin cortar operación.

## Ajuste aplicado en código

- Se mantiene autofill de operación para certificados con prioridad en `is_certificate_type`.
- Se añade dependencia a `oct_certificate_receptions` en `__manifest__.py`.
- Se incorpora tabla técnica `sale.activity.tag.rule` para mapear `activity_type -> tag_id`.
- Si no hay regla, se mantiene fallback por nombre/mapa estático para compatibilidad.

## Comando de Odoo shell para validar datos de picking types certificados por ruta

```python
# Pegar en odoo shell
routes = env['stock.location.route'].sudo().search([])
for route in routes:
    pts = route.rule_ids.mapped('picking_type_id').sorted(key=lambda r: (r.sequence, r.id))
    cert = pts.filtered(lambda p: 'is_certificate_type' in p._fields and p.is_certificate_type)
    if cert:
        print(f"ROUTE {route.id} - {route.display_name}")
        for p in cert:
            print(f"  CERT PT: {p.id} | {p.display_name} | code={p.code}")
```


## UX de asignación masiva (nuevo)

Se añade wizard de uso rápido sobre `sale.order.line` (acción en vista lista) para aplicar actividades en lote a un recordset seleccionado:

- operación `add/remove`,
- selección múltiple de tipos por checkboxes,
- alta masiva evitando duplicados,
- borrado masivo por tipo seleccionado.

Objetivo: cubrir necesidad funcional de asignación sencilla multi-línea sin depender de acciones de servidor dispersas.


## Compatibilidad explícita con `oct_so_line_info`

Para evitar solapes/incompatibilidades con el módulo base ya instalado (`oct_so_line_info`):

- este módulo **depende explícitamente** de `oct_so_line_info`,
- los tipos de actividad en `sale.activity.tag.rule` se toman dinámicamente del campo `sale.activity.type`,
- y el wizard masivo usa esa misma tabla de reglas para operar sobre tipos existentes en la base.

Con esto se evita hardcodear listas que puedan divergir del módulo base.
