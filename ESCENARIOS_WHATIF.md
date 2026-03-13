# Simulación de Escenarios ("What-If") - Documentación

## 📋 Resumen

Se ha implementado exitosamente el sistema de **Simulación de Escenarios** para el planificador de producción. Esta funcionalidad permite a los planificadores crear "borradores" del plan de producción, experimentar con diferentes configuraciones (como agregar pedidos urgentes VIP), y solo publicar el plan cuando estén satisfechos con los resultados.

## ✅ Componentes Implementados

### 1. **Modelo de Datos**
- **Modelo `Scenario`**: Representa un escenario de planificación
  - `nombre`: Nombre descriptivo del escenario
  - `descripcion`: Descripción opcional
  - `es_principal`: Indica si es el Plan Oficial activo
  - `fecha_creacion`: Timestamp de creación

- **Actualización `PrioridadManual`**: 
  - Agregado campo `scenario` (ForeignKey a Scenario)
  - Constraint único actualizado: `(id_orden, maquina, scenario)`
  - Cada override ahora pertenece a un escenario específico

### 2. **Base de Datos**
- Migración `0012_scenario_alter_prioridadmanual_unique_together_and_more.py` aplicada
- Escenario por defecto "Plan Oficial" creado automáticamente
- 50 overrides existentes vinculados al Plan Oficial

### 3. **Backend (Django)**

#### APIs Creadas:
- **`POST /api/scenarios/create/`**: Crear nuevo escenario
  - Parámetros: `nombre`, `descripcion`, `copy_from_id` (opcional)
  - Clona todos los overrides del escenario fuente si se especifica

- **`POST /api/scenarios/<id>/delete/`**: Eliminar escenario
  - Protección: No permite eliminar el Plan Oficial

- **`POST /api/scenarios/<id>/publish/`**: Publicar escenario como oficial
  - Marca el escenario como `es_principal=True`
  - Desmarca todos los demás escenarios

#### Lógica de Planificación:
- `gantt_logic.py` actualizado para filtrar `PrioridadManual` por escenario activo
- Parámetro URL `scenario_id` para seleccionar escenario
- Si no se especifica, usa el escenario marcado como `es_principal`

### 4. **Frontend (UI)**

#### Controles Agregados:
1. **Selector de Escenarios**: Dropdown que muestra todos los escenarios
   - Escenario oficial marcado con ⭐
   - Cambiar escenario recarga la vista con el nuevo plan

2. **Botón "Borrador"**: Crea un nuevo escenario
   - Clona el escenario actual
   - Solicita nombre al usuario
   - Redirige automáticamente al nuevo escenario

3. **Botón "Publicar"**: Publica el escenario actual como oficial
   - Deshabilitado si ya es el plan oficial
   - Confirmación antes de publicar

4. **Botón "Eliminar"**: Elimina el escenario actual
   - Deshabilitado para el plan oficial
   - Confirmación antes de eliminar
   - Redirige al plan oficial tras eliminar

## 🎯 Flujo de Trabajo

### Caso de Uso: Pedido Urgente VIP

1. **Planificador abre el Gantt Visual**
   - Ve el "Plan Oficial" activo

2. **Crea un Borrador**
   - Click en "Borrador"
   - Ingresa nombre: "Plan con Pedido VIP Urgente"
   - Sistema clona el plan oficial

3. **Experimenta con Cambios**
   - Arrastra el pedido VIP al inicio de la cola
   - Ajusta prioridades de otras tareas
   - Ve cómo se retrasan los demás pedidos
   - Puede crear múltiples borradores para comparar

4. **Publica el Mejor Plan**
   - Selecciona el borrador óptimo
   - Click en "Publicar"
   - Confirma la acción
   - El borrador se convierte en el nuevo Plan Oficial

5. **Limpieza**
   - Elimina borradores descartados
   - Mantiene solo escenarios relevantes

## 🔧 Configuración Técnica

### Router de Base de Datos
- `Scenario` agregado a `local_models` en `db_routers.py`
- Escritura permitida en SQLite (default)
- SQL Server permanece read-only

### Inicialización
- Script `init_scenarios.py` para migrar datos existentes
- Crea escenario por defecto si no existe
- Vincula overrides huérfanos al plan oficial

## 📊 Estado Actual

✅ **Completado:**
- Modelo de datos y migraciones
- APIs backend (create, delete, publish)
- UI con selector y botones
- JavaScript para interacciones
- Filtrado por escenario en lógica de planificación
- Clonación de escenarios

⏳ **Pendiente (Opcional):**
- Vista de comparación lado a lado de escenarios
- Historial de cambios entre escenarios
- Permisos de usuario (quién puede publicar)
- Notificaciones cuando se publica un nuevo plan

## 🚀 Próximos Pasos Sugeridos

1. **Probar la Funcionalidad**:
   - Acceder al Gantt Visual
   - Crear un borrador
   - Hacer cambios (drag & drop, pinning)
   - Verificar que los cambios solo afectan el borrador
   - Publicar y verificar que se convierte en oficial

2. **Refinamientos Posibles**:
   - Agregar campo "autor" al modelo Scenario
   - Implementar "modo comparación" visual
   - Agregar timestamps de última modificación
   - Exportar escenarios a Excel

## 📝 Notas Técnicas

- Los errores de lint CSS en el template son falsos positivos (el parser no entiende Django templates)
- Todos los cambios respetan el constraint de SQL Server read-only
- La funcionalidad es completamente retrocompatible
- No se requieren cambios en el frontend existente (drag & drop, pinning, etc.)

## 🎉 Beneficios

1. **Experimentación Sin Riesgo**: Los planificadores pueden probar diferentes configuraciones sin afectar el plan oficial
2. **Trazabilidad**: Cada escenario tiene nombre y descripción
3. **Colaboración**: Múltiples usuarios pueden trabajar en diferentes borradores
4. **Flexibilidad**: Fácil volver atrás si un plan no funciona
5. **Profesionalismo**: Característica esperada en software de planificación empresarial
