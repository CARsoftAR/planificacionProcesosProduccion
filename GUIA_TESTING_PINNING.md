# GUÍA DE TESTING: PINNING MANUAL (Drag & Drop)

## Estado Actual

✅ **Modelo de Base de Datos**: Campo `fecha_inicio_manual` existe en `PrioridadManual`
✅ **Backend API**: Endpoint `/api/set_priority/<id>/` corregido con logging detallado
✅ **Frontend**: Código de drag & drop que calcula y envía la fecha
⚠️ **Problema**: Las fechas NO se están guardando en la base de datos

## Cambios Realizados

### 1. Backend (`views.py` - función `set_priority`)
- **BUG CORREGIDO**: Verificaba `if manual_start_str:` en lugar de `if manual_start_dt is not None:`
- **Logging agregado**: Mensajes detallados con emojis (🔍, ✅, ❌)
- **Validación mejorada**: Devuelve error HTTP 400 si el formato de fecha es inválido
- **Respuesta mejorada**: Devuelve la fecha guardada en el JSON de respuesta

### 2. Excel Export (`views.py` - función `export_planificacion_excel`)
- **Posicionamiento matemático**: Calcula columnas por fecha + hora en lugar de búsqueda lineal
- **Tolerancia a timezone**: Maneja fechas naive/aware correctamente
- **Clipping**: Muestra tareas que empiezan antes del rango visible

### 3. Gantt Logic (`gantt_logic.py`)
- **Rango dinámico**: Expande horarios basándose en tareas reales (no solo config de máquinas)
- **Días forzados**: Incluye días con tareas aunque sean fines de semana

## Pasos para Probar

### Paso 1: Iniciar el Servidor
```bash
python manage.py runserver
```

### Paso 2: Abrir el Gantt Visual
Navega a:
```
http://localhost:8000/planificacion/visual/?proyectos=25-100&run=1
```
(Reemplaza `25-100` con un proyecto real de tu sistema)

### Paso 3: Arrastrar una Tarea
1. Localiza una tarea en el Gantt
2. Haz clic y mantén presionado
3. Arrastra a una nueva posición (diferente hora/día)
4. Suelta el mouse

### Paso 4: Observar la Consola del Servidor
Deberías ver algo como:
```
🔍 DEBUG set_priority ID: 2658
🔍 DEBUG set_priority body: b'{"maquina":"MAC00","new_priority":5500,"manual_start":"2025-12-23 14:30:00"}'
🔍 Parsed - Machine: MAC00, Priority: 5500.0, Manual Start: 2025-12-23 14:30:00
✅ Parsed manual_start_dt: 2025-12-23 14:30:00
🔍 Cleaning old entries for order 2658 except machine MAC00
🔍 Deleted 0 old entries
🔍 Created new PrioridadManual entry
🔍 Updated priority to 5500.0
✅ SAVED manual start date: 2025-12-23 14:30:00
✅ Successfully saved PrioridadManual for order 2658
```

### Paso 5: Verificar en la Base de Datos
```bash
python check_pinning.py
```

Deberías ver:
```
Con fecha manual: 1
Tareas con pinning:
  Orden 2658 -> 2025-12-23 14:30:00 (Maquina: MAC00)
```

### Paso 6: Exportar a Excel
1. Haz clic en "Exportar Excel"
2. Abre el archivo
3. Verifica que la tarea aparece en la misma posición que en el Gantt visual

## Debugging

### Si NO aparecen los logs en la consola:
- El frontend no está llamando al endpoint
- Verifica la consola del navegador (F12) para errores JavaScript
- Busca el mensaje "📌 Attempting PIN: Task..."

### Si aparecen logs pero con errores:
- Revisa el formato de la fecha enviada
- Verifica que `manual_start_dt` no sea `None`

### Si se guarda pero el Excel no coincide:
- Verifica que `gantt_logic.py` esté usando las fechas manuales
- Revisa que `task_force_start_times` se esté poblando correctamente

## Archivos Modificados

1. `produccion/views.py` (líneas 618-690)
2. `produccion/views.py` (líneas 2349-2410) - Excel export
3. `produccion/gantt_logic.py` (líneas 426-500)
4. `produccion/models.py` (líneas 83-88) - Ya existía

## Scripts de Ayuda

- `check_pinning.py`: Verifica el estado del sistema
- `check_manual_dates.py`: Lista todas las fechas manuales guardadas
- `test_pinning.py`: Test manual del endpoint (requiere requests)
