# BITÁCORA DE ERRORES Y MANUAL DE SOLUCIONES TÉCNICAS

Este archivo es un repositorio de conocimiento obligatorio. Actúa como recetario de soluciones para evitar regresiones y resolver rápidamente problemas recurrentes en la plataforma de planificación.

---

## CASO 1: Cruce de variables (Cross-Wiring) "Nivel de Planificación" y "Prioridad Artículos"

**Síntoma:** 
Al modificar la celda "Nivel Planificación" en la tabla (ej. ingresar un 97) y guardar, la recarga de la página mostraba que el 97 se había asignado erróneamente a la columna contigua "Prioridad Artículos". Además, "Nivel Planificación" revertía a su valor original del ERP.

**Causa Raíz:** 
Múltiples capas de sobreescritura incondicional y asignación cruzada:
1. En `produccion/views.py` (y en el duplicado `planificacion/produccion/views.py`), durante la generación del listado, el código inyectaba explícitamente el `nivel_manual` de la base de datos a la variable `prioridad_pieza` (que alimenta la vista).
2. Adicionalmente, el código ignoraba incondicionalmente cualquier override manual para `nivel_planificacion`, aplastándolo sistemáticamente con el valor del ERP.
3. El servicio de lectura SQLite en `services.py` también replicaba este mapeo cruzado.

**RECETA DE SOLUCIÓN (CRÍTICO):**

1. **Backend - Lectura (services.py):**
   Leer cada variable hacia su propio diccionario sin cruces:
   ```python
   op_to_nivel = {p['id_orden']: p['nivel_manual'] for p in p_manual_db if p['nivel_manual'] is not None}
   op_to_prio = {p['id_orden']: p['prioridad'] for p in p_manual_db if p['prioridad'] is not None}
   # ...
   prio = op_to_prio.get(clean_oid)
   - Actualizar el diccionario JS en `planificacion.html` (o `planificacion_visual.html` / `views.py`) para empaquetar por separado los valores del DOM.
   - En `views.py` `planificacion_list` y en `services.py` `guardar_planificacion_manual`, asegurarse de que `nivel_manual` lea `nivel_planificacion` del JSON, y `prioridad` lea el valor real de la prioridad, sin mezclarlos.

2. **Backend - Inyección de Vista (produccion/views.py y planificacion/produccion/views.py):**
   Mapear `nivel_manual` a `nivel_planificacion` (marcando el flag) y `prioridad` a `prioridad_pieza`. Además, prevenir el aplastamiento de `nivel_planificacion` por el valor ERP si hay flag manual.
   ```python
   # 1. Asignar cada variable a su contraparte correcta:
   pieza_priority_val = override_node.get('prioridad')
   
   if override_node.get('nivel_manual') is not None:
       item['nivel_planificacion'] = int(float(override_node['nivel_manual']))
       item['NivelManualFlag'] = True
   else:
       item['NivelManualFlag'] = False

   if pieza_priority_val is not None:
       item['prioridad_pieza'] = int(float(pieza_priority_val))

   # 2. Respetar el override manual frente al ERP:
   if not item.get('NivelManualFlag'):
       erp_nivel = item.get('Nivel_Planificacion')
       item['nivel_planificacion'] = int(erp_nivel) if erp_nivel is not None else 0
   ```

---

## CASO 2: Error de guardado de decimales en porcentaje de Solapamiento (Punto vs Coma)

**Síntoma:** 
Al intentar guardar un valor decimal en el porcentaje de solapamiento (ej. `4.73` o `4,73`), el sistema fallaba, truncaba el valor, o quitaba el punto/coma, resultando en números incorrectos o no se guardaba correctamente en la base de datos. Además, el input de tipo `number` impedía a los usuarios introducir libremente separadores en ciertos navegadores.

**Causa Raíz:** 
1. El input HTML original estaba definido como `<input type="number">`, el cual tiene un comportamiento rígido dependiendo de la configuración regional (locale) del navegador.
2. En frontend (JS), al leer el input para enviar la petición, no se normalizaba el carácter de separador decimal antes de pasarlo al payload (no se reemplazaban comas por puntos).
3. En backend (`produccion/views.py`), el servidor recibía el string e intentaba un cast directo a `float(raw_value)` sin limpiar comas o contemplar strings vacíos, arrojando un `ValueError` o guardando silenciosamente `null`.

**RECETA DE SOLUCIÓN:**

1. **Frontend (HTML/JS):**
   - Cambiar el `<input type="number">` por `<input type="text" inputmode="decimal">`.
   - En la lógica de guardado masivo (JS), reemplazar las comas por puntos antes de extraer el float:
     ```javascript
     let rawSolap = solapInput.value.trim().replace(',', '.');
     let parsedSolap = parseFloat(rawSolap);
     ```

2. **Backend (Python en `views.py`):**
   - Limpiar de forma segura la variable antes de parsear, controlando strings vacíos y validando el separador:
     ```python
     raw_solapamiento = str(porcentaje_solapamiento).strip()
     if raw_solapamiento == '':
         porcentaje_val = 0.0
     else:
         try:
             porcentaje_val = float(raw_solapamiento.replace(',', '.'))
         except ValueError:
             porcentaje_val = 0.0
     ```

---

## CASO 3: Sobreescritura del Orden Manual por Prioridades Automáticas al Guardar

**Síntoma:** 
Al arrastrar tareas manualmente para cambiar su orden en la grilla y presionar "Guardar", el sistema recargaba y las tareas volvían a aparecer en su orden automático por defecto, perdiendo la distribución manual realizada por el usuario.

**Causa Raíz:** 
En el backend (`produccion/views.py`, en el endpoint general de guardado masivo `create_scenario`), el sistema convertía correctamente la posición visual del array (`orden_secuencia`) en un valor matemático de `prioridad`. 
Sin embargo, el frontend enviaba adjunto el valor original de la prioridad ERP en la celda `.row-priority-cell`, y el backend, incondicionalmente, aplastaba el cálculo manual sobrescribiendo `defaults_dict['prioridad'] = prioridad_articulos_final`. Al recargar, la grilla leía esta prioridad automática impuesta.

**RECETA DE SOLUCIÓN:**

Implementación de un aislamiento lógico estricto ("Candado condicional") basado en la bandera de estado de la vista (`plan_mode_payload`).

1. **Backend (`produccion/views.py` en `create_scenario`):**
   - Agregamos una verificación que encapsula la sobreescritura automática. Si el frontend reporta que está enviando el layout en modo `manual`, se interrumpe la asignación del artículo y se respeta íntegramente la prioridad calculada por la secuencia visual.
     ```python
     # Aislamiento Estricto: Si el frontend envía un orden manual explícito, ignoramos el ordenamiento automático
     if plan_mode_payload == 'manual':
         pass # Preservamos defaults_dict['prioridad'] que ya tiene el orden manual (prioridad_val)
     else:
         if prioridad_articulos_final is not None:
             defaults_dict['prioridad'] = prioridad_articulos_final
     ```

2. **Frontend (`produccion/templates/produccion/planificacion.html`):**
   - Confirmamos que al clickear en "Guardar", el frontend extraiga y pase el `ordenamientoMode` en curso, y que tras el éxito, el redireccionamiento mandatorio (`window.location.href = '?scenario_id=...&plan_mode=manual'`) respete la carga asincrónica con la variable protegida por el candado del backend.
