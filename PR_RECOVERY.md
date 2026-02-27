# Recuperación de PR cuando Codex no puede actualizar una PR existente

Si la PR original fue modificada fuera de Codex, la forma segura de continuar es **abrir una PR nueva** desde una rama limpia con los commits válidos.

## Flujo recomendado

1. **Actualizar rama base** (ej. `main` o la rama objetivo):
   - `git fetch --all --prune`
   - `git checkout <base>`
   - `git pull --ff-only`

2. **Crear rama nueva de recuperación**:
   - `git checkout -b fix/sid-activity-recovery`

3. **Traer solo commits buenos** de la rama de trabajo anterior:
   - `git log --oneline <rama_vieja>`
   - `git cherry-pick <commit_1> <commit_2> ...`

   > **¿Qué es `<rama_vieja>`?** Es la rama donde quedó la PR anterior (la que se desincronizó).
   >
   > Ejemplos:
   > - si estabas trabajando en `work`: `git log --oneline work`
   > - si la rama vieja se llamaba `feature/sid-activity`: `git log --oneline feature/sid-activity`
   >
   > Si no recuerdas el nombre:
   > - `git branch --all`
   > - `git reflog --date=iso`

4. **Resolver conflictos y validar**:
   - `python -m py_compile models/sale_activity.py models/activity_tag_rule.py wizard/sale_line_activity_wizard.py hooks.py scripts/odoo_shell_sid_check.py`
   - (Opcional) ejecutar el script de shell:
     - `exec(open('scripts/odoo_shell_sid_check.py').read())`

5. **Push y PR nueva**:
   - `git push -u origin fix/sid-activity-recovery`
   - abrir nueva PR apuntando a `<base>`.


## Caso de tu captura (ramas `codex/review-...`)

Si en GitHub ves ramas como `codex/review-activity-assignment-system-*`, esa es la `<rama_vieja>`.

Ejemplo práctico:

```bash
git fetch --all --prune
git checkout master
git pull --ff-only
git checkout -b fix/sid-activity-recovery

# inspeccionar commits de la rama vieja
git log --oneline origin/codex/review-activity-assignment-system-atafoe

# traer solo los commits que quieres conservar
git cherry-pick <sha1> <sha2>

# push de la rama nueva
git push -u origin fix/sid-activity-recovery
```

Luego abre PR nueva desde `fix/sid-activity-recovery` hacia `master`.

## Recomendaciones para este módulo

- Verificar que la versión de módulo esperada coincide (`__manifest__.py`).
- Confirmar XMLIDs clave del wizard/integración tras upgrade:
  - `sid_view_sale_order_line_tree_wizard_button`
  - `sid_view_sale_order_form_wizard_button`
  - `sid_action_sale_line_activity_wizard`
- Si faltan XMLIDs en BD, ejecutar upgrade del módulo antes de validar UI.

## Mensaje corto para cerrar la PR anterior

> Se cierra esta PR porque fue modificada fuera de Codex y no puede ser actualizada por la plataforma. Se reemplaza por una PR nueva con los mismos cambios, revalidados en rama limpia.
