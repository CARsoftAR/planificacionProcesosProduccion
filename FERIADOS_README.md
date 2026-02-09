# Sistema de Gestión de Feriados

## Descripción

El sistema de gestión de feriados permite administrar los días festivos y configurar cuáles se trabajan en la planificación de producción. Esto es crucial porque algunos feriados la empresa decide trabajar, mientras que otros son días no laborables.

## Características Principales

### 1. **Gestión Completa de Feriados**
- ✅ Crear nuevos feriados
- ✅ Editar feriados existentes
- ✅ Eliminar feriados
- ✅ Activar/Desactivar feriados temporalmente

### 2. **Configuración de Planificación**
- **Se Planifica (Se Trabaja)**: Marcar si un feriado se trabaja
  - `True`: El feriado se incluye en la planificación (día laborable)
  - `False`: El feriado NO se incluye en la planificación (día no laborable)

### 3. **Filtros Avanzados**
- Filtrar por año
- Filtrar por estado (pasados/futuros/todos)
- Filtrar por planificación (se trabajan/no se trabajan/todos)

### 4. **Estadísticas en Tiempo Real**
- Total de feriados registrados
- Cantidad de feriados que se trabajan
- Cantidad de feriados que no se trabajan

### 5. **Integración con Planificación**
El sistema de planificación automáticamente:
- **Salta** los feriados marcados como "No se trabaja" (`se_planifica=False`)
- **Incluye** los feriados marcados como "Se trabaja" (`se_planifica=True`)

## Uso

### Acceder al Sistema
1. Desde el menú principal, seleccionar **"Feriados"**
2. Se mostrará la lista de todos los feriados registrados

### Crear un Nuevo Feriado
1. Click en **"Nuevo Feriado"**
2. Completar el formulario:
   - **Fecha**: Seleccionar la fecha del feriado
   - **Descripción**: Nombre del feriado (ej: "Día de la Independencia")
   - **¿Se Trabaja?**: Marcar si este feriado se trabaja
   - **Activo**: Marcar para activar el feriado
3. Click en **"Crear Feriado"**

### Editar un Feriado
1. En la lista de feriados, click en el botón **✏️ (Editar)**
2. Modificar los campos necesarios
3. Click en **"Guardar Cambios"**

### Cambiar Estado Rápidamente
- **Toggle "Se Trabaja"**: Click en el switch para cambiar si el feriado se planifica
- **Toggle "Activo"**: Click en el switch para activar/desactivar el feriado

### Eliminar un Feriado
1. Click en el botón **🗑️ (Eliminar)**
2. Confirmar la eliminación

> **Nota**: Si solo desea desactivar temporalmente un feriado, use el toggle "Activo" en lugar de eliminarlo.

## Datos de Ejemplo

Para cargar feriados de ejemplo (Argentina 2025), ejecutar:

```bash
python manage.py shell < create_sample_holidays.py
```

Este script crea:
- 16 feriados nacionales de Argentina 2025 (no laborables)
- 2 feriados especiales que se trabajan (Nochebuena y Fin de Año medio día)

## Modelo de Datos

### Campos del Modelo `Feriado`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `fecha` | DateField | Fecha del feriado (única) |
| `descripcion` | CharField(200) | Nombre/descripción del feriado |
| `se_planifica` | BooleanField | Si se trabaja este feriado (default: False) |
| `activo` | BooleanField | Si el feriado está activo (default: True) |
| `fecha_creacion` | DateTimeField | Fecha de creación del registro |
| `fecha_modificacion` | DateTimeField | Última modificación |

### Propiedades Calculadas

- `es_pasado`: Indica si el feriado ya pasó
- `es_futuro`: Indica si el feriado es futuro

## Integración con Planificación

El sistema de planificación utiliza la función `is_non_working_holiday(date)` para verificar si una fecha es feriado no laborable.

### Lógica de Planificación

```python
# Durante el cálculo de timeline
if is_non_working_holiday(current_time):
    # Saltar al día siguiente
    current_time = next_day
    continue
```

### Criterios para Considerar un Feriado

Un día se considera **feriado no laborable** si cumple:
1. ✅ Existe un registro de `Feriado` para esa fecha
2. ✅ El feriado está `activo=True`
3. ✅ El feriado tiene `se_planifica=False` (NO se trabaja)

## API Endpoints

### Vistas Web
- `GET /feriados/` - Lista de feriados
- `GET /feriados/crear/` - Formulario de creación
- `POST /feriados/crear/` - Crear feriado
- `GET /feriados/<id>/editar/` - Formulario de edición
- `POST /feriados/<id>/editar/` - Actualizar feriado
- `GET /feriados/<id>/eliminar/` - Confirmación de eliminación
- `POST /feriados/<id>/eliminar/` - Eliminar feriado

### API AJAX
- `POST /api/feriados/<id>/toggle-planifica/` - Cambiar estado de planificación
- `POST /api/feriados/<id>/toggle-activo/` - Cambiar estado activo

## Ejemplos de Uso

### Ejemplo 1: Feriado Nacional (No se trabaja)
```
Fecha: 09/07/2025
Descripción: Día de la Independencia
Se Planifica: ❌ No
Activo: ✅ Sí
```
**Resultado**: El 9 de julio no se planificarán tareas.

### Ejemplo 2: Día Especial (Se trabaja)
```
Fecha: 24/12/2025
Descripción: Nochebuena (Medio día)
Se Planifica: ✅ Sí
Activo: ✅ Sí
```
**Resultado**: El 24 de diciembre se planificarán tareas normalmente.

### Ejemplo 3: Feriado Desactivado
```
Fecha: 01/01/2025
Descripción: Año Nuevo
Se Planifica: ❌ No
Activo: ❌ No
```
**Resultado**: El feriado existe pero está desactivado, se tratará como día normal.

## Buenas Prácticas

1. **Planificación Anual**: Cargar todos los feriados del año al inicio
2. **Revisión Periódica**: Verificar feriados trasladados o especiales
3. **Documentación**: Usar descripciones claras (ej: "Carnaval - Lunes")
4. **Desactivar vs Eliminar**: Preferir desactivar feriados en lugar de eliminarlos
5. **Comunicación**: Informar al equipo sobre cambios en feriados laborables

## Troubleshooting

### Problema: El feriado no se respeta en la planificación
**Solución**: Verificar que:
- El feriado esté `activo=True`
- El feriado tenga `se_planifica=False`
- La fecha sea correcta

### Problema: No puedo crear un feriado duplicado
**Solución**: Ya existe un feriado para esa fecha. Editar el existente o eliminarlo primero.

### Problema: Los cambios no se reflejan en el Gantt
**Solución**: Refrescar la página de planificación visual después de modificar feriados.

## Soporte

Para más información o reportar problemas, contactar al equipo de desarrollo.

---

**Versión**: 1.0  
**Última actualización**: Diciembre 2025  
**Sistema**: ABBAMAT - Planificación de Procesos Productivos
