# 📋 RELEVAMIENTO DEL PROYECTO — Planificación de Procesos Productivos
## Documento de Traspaso para OpenCode AI

---

## 🏗️ DESCRIPCIÓN GENERAL DEL SISTEMA

Sistema de **planificación de producción industrial** construido con Django. Permite:
- Visualizar un Gantt interactivo de operaciones de producción por máquina.
- Planificar órdenes de producción (OPs) respetando horarios de máquinas, dependencias entre OPs y feriados.
- Administrar escenarios de planificación alternativos.
- Registrar mantenimientos de máquinas.
- Mostrar la ruta crítica (critical path) de cada proyecto en el Gantt.

### Stack Tecnológico
- **Backend**: Django (Python), en `c:\Sistemas ABBAMAT\planificacionProcesosProductivos\`
- **Frontend**: HTML + CSS (glassmorphism premium) + JavaScript vanilla + Bootstrap 5 + SweetAlert2
- **Bases de datos**:
  - `default` → SQLite local (modelos propios del sistema: planificación, escenarios, mantenimientos, feriados)
  - `production` → SQL Server externo, **READ-ONLY** (datos ERP: órdenes, operaciones, máquinas, materiales)

---

## 📁 ARCHIVOS CLAVE

| Archivo | Rol |
|---|---|
| `produccion/planning_service.py` | ⭐ Motor de cálculo de timelines por máquina. Respeta horarios (LV/SA), feriados y mantenimientos. |
| `produccion/gantt_logic.py` | ⭐ Orquesta la generación del Gantt completo. Agrupa tareas por máquina, calcula posiciones visuales en px, implementa critical path. |
| `produccion/views.py` | Todas las vistas Django: API endpoints, carga de datos, planificación, exportación Excel, etc. |
| `produccion/models.py` | Modelos locales: `Scenario`, `PrioridadManual`, `HorarioMaquina`, `Feriado`, `MantenimientoMaquina`, `OrdenPlanificada`. |
| `produccion/templates/produccion/planificacion_visual.html` | ⭐ Template principal del Gantt (2900+ líneas). Gantt + tooltips + drag & drop + critical path visual. |
| `planificacion/db_routers.py` | Router que separa qué modelos van a SQLite (default) vs SQL Server (production). |
| `planificacion/settings.py` | Configuración Django. Define las dos bases de datos. |

---

## ✅ LO QUE ESTÁ FUNCIONANDO

### 1. Gantt Visual Premium
- Gantt interactivo con columnas por hora, filas por máquina.
- Tareas renderizadas como bloques con colores por proyecto.
- Tooltip detallado por tarea (fechas, avance, solapamiento, estado).
- Bloques de mantenimiento (fondo rayado rojo) sobre la máquina correspondiente.
- Línea vertical del "ahora" (simulación).
- Scroll sincronizado entre header de horas y body de tareas.
- Dependencias entre tareas dibujadas con SVG (flechas).

### 2. Motor de Planificación (`planning_service.py`)
- Calcula `start_date` y `end_date` de cada tarea respetando:
  - Horarios LV (lunes-viernes) y SA (sábado) configurados por máquina.
  - Feriados no laborables (tipo `NO`) y de medio día (tipo `MEDIO`, límite 12hs).
  - Mantenimientos activos de la máquina.
- Genera **segmentos**: si una tarea cruza el fin de turno, se parte en dos bloques visuales.
- Respeta dependencias entre OPs (`task_min_start_times`).
- Respeta "pins" (inicio forzado manual, `task_force_start_times`).
- Respeta solapamiento configurado (`porcentaje_solapamiento`).

### 3. Escenarios
- Se puede crear/cambiar entre múltiples escenarios de planificación.
- Cada escenario tiene sus propias prioridades manuales y pins.

### 4. Módulo de Mantenimiento
- CRUD de mantenimientos de maquina (`MantenimientoMaquina`).
- Correctamente ruteado a la DB `default` (SQLite).
- Se muestran como bloques en el Gantt.

### 5. Análisis de Ruta Crítica (Critical Path)
- **Backend** (`gantt_logic.py`): Identifica la cadena de tareas que determina la fecha de entrega de cada proyecto. Marca `is_critical=True` en cada segmento.
- **Frontend** (`planificacion_visual.html`):
  - Tareas críticas tienen animación pulsante rojo/naranja (`criticalPulse`).
  - Badge "🔥 Ruta Crítica" visible sobre la tarea.
  - El tooltip de la tarea muestra el badge "RUTA CRÍTICA" en rojo.
  - Botón flotante "🔥 Ruta Crítica" en la esquina inferior derecha con contador de tareas críticas.
  - Al hacer clic en el botón, las tareas NO críticas se atenúan para ver sólo la cadena crítica.

### 6. Funcionalidades de UI
- Drag & drop de tareas para mover su inicio.
- Click derecho para opciones contextuales.
- Exportación a Excel del Gantt.
- Replanificación desde diferentes puntos de inicio.
- Filtros por escenario.

---

## 🐛 BUG ACTIVO — NO RESUELTO (PRIORIDAD ALTA)

### Bug: Tareas sobrepasan el límite horario del sábado (y posiblemente otros días)

**Síntoma:** Máquinas con horario SA de 07:00 a 13:00 muestran tareas que terminan después de las 13:00 en el Gantt visual.

**Archivo afectado:** `produccion/planning_service.py`

**Sección problemática:** función `calculate_timeline()`, bloque `if is_working_time:` (aprox. líneas 320-400)

**Causa raíz investigada pero NO CONFIRMADA:** El cálculo de `available_hours` con `timedelta` puede tener drift de punto flotante. Se intentaron múltiples fixes:

1. **Fix 1 (no resolvió):** Agregar verificación `if new_time > shift_end_dt: new_time = shift_end_dt` después de calcular `new_time`.

2. **Fix 2 (ACTUAL - en el código ahora):** 
   - Se calcula `shift_end_dt = datetime.combine(current_time.date(), _e_now)` para el día actual.
   - Si `segment_will_end_at_shift_boundary == True`, se hace **snap directo**: `current_time = shift_end_dt` (sin timedelta, sin aritmética flotante).
   - El bloque de creación de segmento también tiene una triple defensa: `if segment_end > shift_end_dt: segment_end = shift_end_dt`.

**Lo que hay que verificar:** Si el bug persiste aún con el Fix 2 en producción. Si sí persiste, es probable que el problema esté en OTRO lugar — posiblemente en `gantt_logic.py` donde se calculan `visual_left` y `visual_width` en píxeles, o en cómo el frontend renderiza los bloques.

**Cómo reproducir:** 
1. Tener una máquina con horario SA 07:00-13:00 configurado.
2. Tener una tarea que se planifique en el sábado.
3. Ver el Gantt y verificar si el bloque termina en la columna "13" o más a la derecha.

**Líneas de código actuales del fix (planning_service.py ~365-400):**
```python
_e_now = schedules[day_type]['end'] if (day_type and day_type in schedules) else None
if _e_now and is_half_day_holiday(current_time, half_day_holidays):
    _e_now = datetime.strptime("12:00", "%H:%M").time()
shift_end_dt = datetime.combine(current_time.date(), _e_now) if _e_now else None

if segment_will_end_at_shift_boundary and shift_end_dt:
    if segment_start:
        time_to_consume = max(0.0, (shift_end_dt - segment_start).total_seconds() / 3600.0)
    current_time = shift_end_dt
else:
    current_time = current_time + timedelta(hours=time_to_consume)
    if shift_end_dt and current_time > shift_end_dt:
        current_time = shift_end_dt

remaining_hours -= time_to_consume

if remaining_hours <= 0.001 or segment_will_end_at_shift_boundary:
    segment_end = current_time
    if shift_end_dt and segment_end > shift_end_dt:
        segment_end = shift_end_dt
```

---

## 📋 ROADMAP — LO QUE FALTA IMPLEMENTAR

### PRIORIDAD 1 — Bug horarios (ver arriba)
Resolver definitivamente que las tareas no sobrepasan el límite de horario del turno.

### PRIORIDAD 2 — Alertas Predictivas
**Objetivo:** Notificar automáticamente cuando un proyecto está en riesgo de retraso.

**Cómo funcionar:**
- Comparar la fecha de fin planificada de la última tarea de cada proyecto vs. la fecha de entrega comprometida (`FechaEntrega` en la OP del SQL Server).
- Si la diferencia es negativa (planificado termina después de lo comprometido), generar una alerta.
- Las alertas deberían mostrarse:
  - Como un badge/indicador en el Gantt sobre las tareas afectadas.
  - Como un panel de alertas resumen (lista de proyectos en riesgo con días de retraso).
- **Archivo a modificar:** `gantt_logic.py` para calcular y añadir `is_delayed` y `days_delay` a los proyectos; `planificacion_visual.html` para renderizarlos.

### PRIORIDAD 3 — Integración de Inventario
**Objetivo:** Antes de confirmar una tarea planificada, verificar si hay stock de materia prima.

**Estado:** No iniciado.

### PRIORIDAD 4 — Dashboard de Eficiencia (OEE)
**Objetivo:** Métricas avanzadas sobre uso real vs. planeado de la planta.

**Estado:** No iniciado.

### PRIORIDAD 5 — Capacidad Adaptativa
**Objetivo:** Ante una falla de máquina, redistribuir automáticamente las tareas a otras máquinas compatibles.

**Estado:** No iniciado.

---

## 🗄️ MODELO DE DATOS CLAVE (SQLite local)

```python
# models.py (produccion/models.py)

class Scenario(models.Model):
    nombre = CharField
    activo = BooleanField
    fecha_creacion = DateTimeField

class PrioridadManual(models.Model):
    scenario = FK(Scenario)
    id_orden = CharField  # ID de la OP del SQL Server
    prioridad = IntegerField  # 1=primero

class HorarioMaquina(models.Model):
    maquina = FK(...)  # ID de la máquina del SQL Server (usada como referencia)
    dia = CharField  # 'LV' o 'SA'
    hora_inicio = TimeField
    hora_fin = TimeField

class Feriado(models.Model):
    fecha = DateField
    descripcion = CharField
    activo = BooleanField
    tipo_jornada = CharField  # 'NO' (no labora) o 'MEDIO' (hasta 12hs)

class MantenimientoMaquina(models.Model):
    maquina_id = CharField
    motivo = TextField
    fecha_inicio = DateTimeField
    fecha_fin = DateTimeField
    estado = CharField  # 'PROGRAMADO', 'EN_CURSO', 'FINALIZADO'
```

---

## 🔄 FLUJO DE DATOS — Cómo se genera el Gantt

1. **Vista** (`views.py` → `planificacion_visual`) llama a `gantt_logic.get_gantt_data()`.
2. **gantt_logic** carga máquinas y tareas del SQL Server.
3. Aplica prioridades del `Scenario` activo (reordena las tareas por máquina).
4. Para cada máquina, llama a `planning_service.calculate_timeline()`.
5. `calculate_timeline` genera segmentos con `start_date`, `end_date`, etc.
6. `gantt_logic` convierte fechas a píxeles (`visual_left`, `visual_width`).
7. `gantt_logic` ejecuta el análisis de **Critical Path** (marca `is_critical`).
8. El resultado (`timeline_data`) se pasa al template Django.
9. El template renderiza los bloques HTML con estilos inline de posición en px.

---

## ⚠️ NOTAS IMPORTANTES

1. **SQL Server es READ-ONLY.** Nunca intentar escribir datos allí. Todos los datos de configuración/planificación van a SQLite (`default`).

2. **El linter Pyre2 muestra muchos errores en estos archivos** — son TODOS falsos positivos por no tener el path de Django configurado en el analizador. El código funciona correctamente en Python.

3. **El sistema tiene dos servidores Django corriendo** (`manage.py runserver`). Esto es normal en el entorno de desarrollo del usuario.

4. **Feriados**: El modelo `Feriado` tiene `tipo_jornada`:
   - `'NO'` = día no laborable completo.
   - `'MEDIO'` = se trabaja hasta las 12:00 hs.

5. **Segmentos**: Una tarea que cruza el fin de un turno genera múltiples "segmentos" (uno por día/turno). El atributo `segment_index` indica cuál es (0 = primero). Los segmentos de continuación (`segment_index > 0`) tienen clase CSS `task-continuation` y apariencia más tenue.

6. **El campo `Tiempo_Proceso`** en las tareas es la duración total en horas de la OP (ya descontando lo producido). Es el campo real que se usa para la planificación.

---

## 🚀 CÓMO ARRANCAR EL SERVIDOR

```bash
cd "c:\Sistemas ABBAMAT\planificacionProcesosProductivos"
python manage.py runserver
```

URL del Gantt: `http://127.0.0.1:8000/produccion/planificacion-visual/`

---

*Generado el 19/03/2026 — Estado del código al momento de este handoff.*
