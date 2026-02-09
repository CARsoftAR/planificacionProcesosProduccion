# Project Memory: Planificación de Procesos Productivos

Este archivo rastrea las decisiones de diseño, las pruebas realizadas y las funcionalidades implementadas, permitiendo iterar y probar diferentes enfoques sin perder el contexto.

## Estado Actual
**Fecha:** 18 de Diciembre, 2025
**Objetivo:** Implementar "Gestión de Dependencias entre Tareas" - 🔄 **OPCIÓN A IMPLEMENTADA**

## Opciones de Implementación Evaluadas

### Opción A: Automática (Basado en Número de Operación) ✅ **IMPLEMENTADA**
*   **Descripción:** Usar el campo `NumeroOperacion` del SQL Server para vincular tareas secuencialmente de forma automática.
*   **Lógica:** Dentro de cada orden (Mstnmbr), las operaciones se vinculan automáticamente: Op10 → Op20 → Op30 → Op40
*   **Estado:** **ACTIVA** - Implementada el 18/12/2025
*   **Ventajas:**
    - ✅ Completamente automática - sin intervención del usuario
    - ✅ Basada en datos existentes en SQL Server
    - ✅ Lógica estándar de manufactura
    - ✅ Simple y directa

### Opción B: Basado en Recetas (Rutas Maestras)
*   **Descripción:** Definir rutas estándar por producto.
*   **Estado:** No implementada (Opción A selected).

### Opción C: Manual (Visual) - ❌ **DESACTIVADA**
*   **Descripción:** El usuario crea vínculos manualmente desde la interfaz visual (Gantt).
*   **Estado:** **Implementada pero desactivada** - No funcionaba correctamente
*   **Problemas encontrados:**
    - Click en tareas no generaba feedback visual consistente
    - Interfaz compleja para el usuario
    - Requería demasiada intervención manual
*   **Acción:** Código comentado/desactivado, reemplazado por Opción A

## Log de Cambios (Implementation Log)

### ✅ Implementación Opción A (18 Diciembre 2025)

1. **Modificación de `services.py`**
   - ✅ Agregado campo `NumeroOperacion` a la query SQL
   - Query actualizada para incluir: `Isnull(T.NumeroOperacion, 0) AS NumeroOperacion`

2. **Lógica Automática en `views.py`** (`planificacion_visual`)
   - ✅ Obtener todas las tareas con `get_planificacion_data({})`
   - ✅ Agrupar tareas por `Mstnmbr` (número de orden)
   - ✅ Ordenar tareas dentro de cada orden por `NumeroOperacion`
   - ✅ Crear cadena de dependencias: Op[i] depende de Op[i-1]
   - ✅ Validaciones: Solo vincular si OpNum[i] > OpNum[i-1]
   - ✅ Construir `dependency_map: {successor_id: [predecessor_id]}`

3. **Aplicación en Planificación (DOS PASADAS)**
   - ✅ **Primera Pasada:** Calcular todas las tareas SIN dependencias → construir `global_task_end_dates`
   - ✅ **Segunda Pasada:** Recalcular tareas con dependencias usando tiempos correctos
   - ✅ Funciona cross-machine (tareas en diferentes máquinas)

4. **Exportación a Excel**
   - ✅ Misma lógica aplicada en `export_planificacion_excel`
   - ✅ Dependencias reflejadas en el Gantt exportado

5. **Visualización**
   - ✅ Flechas SVG automáticas entre operaciones vinculadas
   - ✅ JSON de dependencias generado desde `dependency_map`

## Funcionalidad Actual

### Cómo Funcionan las Dependencias Automáticas

**Ejemplo:**
```
Orden 45123:
- Op 10 (Corte)     → ID: 45123-10
- Op 20 (Soldadura) → ID: 45123-20
- Op 30 (Pintura)   → ID: 45123-30
- Op 40 (Ensamble)  → ID: 45123-40

Dependencias Automáticas:
45123-20 depende de 45123-10
45123-30 depende de 45123-20
45123-40 depende de 45123-30
```

**Resultado:**
- La Operación 20 **NO PUEDE** empezar hasta que termine la Operación 10  
- La Operación 30 **NO PUEDE** empezar hasta que termine la Operación 20
- Y así sucesivamente...

**Visualización:**
- Flechas automáticas en el Gantt visual
- Las tareas se programan respetando las dependencias

## Notas Técnicas

- **Base de Datos Local (SQLite):** Ya no se usa para dependencias (solo para prioridades y configuración de máquinas)
- **SQL Server (Solo Lectura):** Campo `NumeroOperacion` se lee de aquí
- **Algoritmo:** `planning_service.calculate_timeline()` respeta horarios, feriados Y dependencias
- **Performance:** Dos pasadas aseguran que dependencias funcionen correctamente incluso cross-machine
- **Logs:** Mensajes de consola muestran cada dependencia creada automáticamente

## Próximos Pasos (Opcional)

- [ ] Agregar toggle UI para activar/desactivar dependencias automáticas
- [ ] Implementar Opción B (Recetas Maestras) para casos más complejos
- [ ] Permitir excepciones manuales a las dependencias automáticas
