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

---

## CASO 4: Contaminación Visual de "Prioridad Artículos" con la Matemática de Ordenamiento Manual

**Síntoma:**
Al usar la funcionalidad de reordenamiento manual (drag-and-drop), los valores de la columna "Prioridad Artículos" en la tabla principal se reemplazaban por números inflados (1000, 2000, 3000...), ocultando el valor real de la prioridad asignada a la pieza desde el Selector de Producción.

**Causa Raíz:**
Conflicto de re-utilización de campos en base de datos.
1. El endpoint del modal de tareas nuevas (`api_confirm_selected_tasks`) recibía la "Prioridad Pieza" y la guardaba correctamente en la columna `prioridad` del modelo `PrioridadManual`.
2. Sin embargo, cuando se reordenaban las filas, el sistema matemático guardaba los saltos de indexación visuales (los múltiplos de 1000) **en esa misma columna `prioridad`**.
3. Al recargar la vista, `planificacion_list` tomaba ciegamente el valor guardado en `prioridad` e inyectaba los múltiplos de 1000 de vuelta al frontend, asumiendo que eran las prioridades legítimas de las piezas.

**RECETA DE SOLUCIÓN:**

1. **Backend - Reconexión y Escudo Lógico (`produccion/views.py` en `planificacion_list`):**
   - Identificamos que el valor que viaja bajo `pieza_priority_val` contiene tanto la prioridad real de la pieza (1, 2, 3...) como la contaminación matemática si hubo drag-and-drop (>= 1000).
   - Mapeamos nuevamente `pieza_priority_val` a la celda visual `prioridad_pieza` introduciendo una capa de filtrado:
     ```python
     # Reconexión visual al valor del modal guardado en 'prioridad' (pieza_priority_val)
     # Ocultamos la matemática de ordenamiento (saltos >= 1000) de la columna visual
     if pieza_priority_val is not None and float(pieza_priority_val) < 1000:
         item['prioridad_pieza'] = int(float(pieza_priority_val))
     elif item.get('prioridad_pieza') is None or float(item.get('prioridad_pieza', 0)) >= 1000:
         item['prioridad_pieza'] = 1 # Respaldo visual si fue pisado por el drag-and-drop
         
     item['orden_manual_index'] = float(pieza_priority_val) if pieza_priority_val is not None else 0
     ```
   - De esta forma, las matemáticas del orden quedan estrictamente enjauladas en `orden_manual_index` para el motor del Gantt, mientras que la tabla visual solo renderiza las prioridades legítimas.
---

## CASO 5: Sobreescritura del Orden Descendente de Nivel de Planificación por Modo Manual

**Síntoma:**
A pesar de modificar la consulta SQL nativa (`ORDER BY Nivel_Planificacion DESC`), la tabla en pantalla continuaba ordenándose de menor a mayor en esa columna (ej. 4, 5, 11, 12, 14), ignorando el ordenamiento descendente solicitado.

**Causa Raíz:**
Reordenamiento secundario (downstream) ciego en Python para tareas no arrastradas.
1. Al usar el modo "manual" (ej. después de guardar un Drag-and-Drop), el frontend enviaba `plan_mode=manual`.
2. En `produccion/views.py` (`planificacion_list`), la "inyección de fuerza bruta" del orden forzaba un `.sort()` sobre todas las tareas usando la variable `OrdenVisual`.
3. Las tareas que *no* habían sido movidas manualmente poseían el valor por defecto `OrdenVisual = 1000.0`. Al empatar todas en este valor, el desempate natural de la función `.sort()` en Python recaía **exclusivamente** sobre el `Idorden` (`x.get('Idorden', 0)`).
4. Como las órdenes se insertan de forma secuencial en el ERP, su `Idorden` creciente correlacionaba exactamente con su `Nivel_Planificacion` ascendente. Esto produjo la ilusión óptica de que la columna se estaba forzando de menor a mayor.

**RECETA DE SOLUCIÓN:**
Se reparó el bloque de ordenamiento del modo "manual" en `produccion/views.py` para inyectar explícitamente toda la jerarquía de desempate en lugar de confiar solo en el `Idorden`.

```python
# ANTES: El empate en modo manual recaía en Idorden (ASC)
lista_tareas.sort(key=lambda x: (
    float(x.get('OrdenVisual') ...),
    x.get('Idorden', 0)
))

# DESPUÉS: Fallback estructurado garantizando la jerarquía oficial
lista_tareas.sort(key=lambda x: (
    float(x.get('OrdenVisual') ...),
    int(x.get('prioridad_proyecto', x.get('ProyectoCode', 0)) ...),
    int(x.get('prioridad_articulo', x.get('prioridad_pieza', 0)) ...),
    -int(x.get('nivel_planificacion', x.get('Nivel_Planificacion', 0)) ...),
    x.get('Idorden', 0)
))
```

---

## CASO 6: Desincronización del Motor de Renderizado del Gantt (Pérdida del DOM de Origen)

**Síntoma:**
Al ordenar manualmente las tareas en la tabla (`planificacion.html`), la tabla respetaba el orden correctamente. Sin embargo, al abrir el Gantt en otra pestaña o ventana (`planificacion_visual.html`), el gráfico mostraba los bloques en el orden original del backend, ignorando el orden visual de la tabla.

**Causa Raíz:**
El motor de Auto-Layout (`runAutoLayout`) intentaba buscar el DOM de la tabla a través de `window.opener` o `window.parent` para extraer el orden visual actualizado mediante el atributo `data-id`. Al ejecutarse una navegación completa (cambio de página), el documento original (la tabla) ya no existía en memoria, los selectores devolvían arrays vacíos, y el ordenamiento visual fallaba silenciosamente aplicando el "fallback" a todas las tareas.

**RECETA DE SOLUCIÓN:**
Se utilizó `sessionStorage` para guardar el estado del orden visual justo antes de abandonar la página.
1. En `planificacion.html` (función `openGantt`), capturar el DOM visual y serializarlo por máquina:
```javascript
const orderMap = {};
document.querySelectorAll('tbody tr[data-id][data-maquina]').forEach(tr => {
    const mid = tr.getAttribute('data-maquina');
    if (!orderMap[mid]) orderMap[mid] = [];
    orderMap[mid].push(tr.getAttribute('data-id'));
});
sessionStorage.setItem('ganttTableOrder', JSON.stringify(orderMap));
```
2. En `planificacion_visual.html` (`runAutoLayout`), recuperar este mapa de orden en lugar de intentar acceder a un DOM que ya no existe y utilizar ese arreglo como fuente de verdad del orden.

---

## CASO 7: Sobreescritura del "origLeft" precalculado del Backend en Bloques Empujados

**Síntoma:**
Al ordenar manualmente un bloque que originalmente estaba muy adelante en el tiempo hacia el principio, el gráfico mostraba el bloque en la posición correcta visualmente, pero se empujaba hacia un punto temporal equivocado.

**Causa Raíz:**
El algoritmo de posicionamiento de `runAutoLayout` iteraba sobre los bloques ordenados, pero usaba el estilo `left` original (calculado por el backend, `origLeft`) como punto de inicio (targetLeft) antes de verificar solapes.
Si el backend calculaba un bloque A en px=200 y el bloque B en px=0, y el sort visual los ponía [A, B], el algoritmo posicionaba A en 200, y B en 0 (que al ser < 200, lo empujaba a 209). El orden quedaba [A, B] pero arrancaban en 200px en lugar de la posición cero.

**RECETA DE SOLUCIÓN:**
Se modificó `runAutoLayout` para que ignore el `origLeft` del backend para todos los bloques subsecuentes, encadenándolos de forma estricta.
1. Se determina el `anchorLeft` (el mínimo `origLeft` de todos los bloques, que marca el inicio real).
2. El primer bloque se coloca en el `anchorLeft`.
3. Todos los siguientes se colocan en `cursor`, donde `cursor = final del bloque anterior + margen`.

---

## CASO 8: Sobreescritura del Sort Global en Backend en Modo Manual

**Síntoma:**
El ordenamiento manual fallaba y la pantalla del Gantt siempre mostraba un orden basado en prioridades matemáticas a pesar de que el código JS estaba correcto.

**Causa Raíz:**
En `gantt_logic.py`, el bloque de código ejecutaba dos ordenamientos:
1. Un sort por máquina que respetaba el `OrdenVisual` en modo manual.
2. Un sort GLOBAL (`all_global_tasks.sort`) ejecutado más abajo que, incondicionalmente sin importar el modo, imponía la jerarquía: Proyecto -> Artículo -> Nivel DESC. Este segundo sort global aplastaba el esfuerzo del primer sort.

**RECETA DE SOLUCIÓN:**
Se separó la lógica del sort global en `gantt_logic.py` basándose en el modo de planificación.
Si no es modo `original` (es decir, modo manual), el sort global también debe respetar primariamente el orden del usuario:
```python
if plan_mode != 'original':
    all_global_tasks.sort(key=lambda x: (
        x.get('OrdenSecuencia', 999999),
        x.get('OrdenVisual', 999999),
        # ... fallbacks
    ))
```

---

## CASO 9: Gantt No Refleja Cambios sin Guardar Previamente

**Síntoma:**
Tras arreglar todos los conflictos de orden, si el usuario arrastraba una tarea en la tabla y le daba "Abrir Gantt" sin guardar, el gráfico no aplicaba los cambios visuales, mostrando el orden antiguo.

**Causa Raíz:**
El motor `runAutoLayout` en `planificacion_visual.html` estaba condicionado en el template HTML de la siguiente manera:
```html
{% if plan_mode == 'original' %}
    setTimeout(runAutoLayout, 850);
{% endif %}
```
En modo manual, no se llamaba, confiando erróneamente que el orden que venía del backend ya era el final.

**RECETA DE SOLUCIÓN:**
Se removió la condición de Django. `runAutoLayout` debe ejecutarse SIEMPRE al cargar la página (independientemente del modo) para que aplique el mapa de orden de la sesión del usuario (capturado en el `sessionStorage`).

---

## CASO 10: Compresión Errónea de Fragmentos de una Misma Tarea (Pérdida de Fines de Semana/Noches)

**Síntoma:**
Tareas de larga duración que superaban un turno y debían continuar al día siguiente (divididas por el backend correctamente en dos fragmentos antes y después de la noche), se renderizaban visualmente en el mismo día. Aparecían como dos pequeños bloques continuos conectados por la línea punteada de fragmentación pero sin el espacio temporal correspondiente a la noche o fin de semana.

**Causa Raíz:**
El motor `runAutoLayout` introducido en el front-end iteraba ciegamente sobre todos los elementos `.task-block`. Al encadenar las tareas (forzando `targetLeft = cursor`), este algoritmo arrastraba todos los fragmentos hacia la izquierda hasta tocar el fragmento anterior. 
Si el backend calculaba que un fragmento iniciaba el Viernes (100px) y su continuación el Lunes (500px), el motor visual arrastraba el bloque del Lunes inmediatamente después del del Viernes (ej. a los 150px), eliminando por completo la escala de tiempo generada por el calendario de días no laborables del backend.

**RECETA DE SOLUCIÓN:**
Se agregó inteligencia contextual al motor de Auto-Layout (`runAutoLayout`) en `planificacion_visual.html` para detectar si múltiples fragmentos pertenecen a la MISMA tarea (`data-task-id`).
En caso afirmativo, en lugar de pegarlos a la izquierda, el script lee la distancia temporal original calculada por el backend entre esos dos fragmentos y la mantiene rígidamente:

```javascript
if (taskId === previousTaskId && previousOriginalLeft !== null && previousTargetLeft !== null) {
    // Preservar la distancia temporal exacta (ej. la noche o fin de semana) que calculó el backend
    const distance = currentLeft - previousOriginalLeft;
    targetLeft = previousTargetLeft + distance;
} else {
    // Si es una OP diferente, arranca donde terminó el anterior + margen
    targetLeft = cursor;
}
```
De esta forma, los saltos temporales obligatorios de la fábrica se respetan, mientras que los bloques independientes continúan resolviendo el solapamiento de forma dinámica.
