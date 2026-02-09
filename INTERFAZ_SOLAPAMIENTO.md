# 🎯 Interfaz Visual de Solapamiento - Guía de Uso

## ✨ Nueva Funcionalidad Agregada

Ahora puedes configurar el porcentaje de solapamiento directamente desde el scheduler visual con **un simple clic derecho** en cualquier tarea.

## 🖱️ Cómo Usar

### Paso 1: Abrir el Configurador
1. Ve a **Planificación Visual** (`/planificacion/visual/`)
2. Haz **clic derecho** en cualquier tarea del Gantt
3. Se abrirá el modal de "Configurar Solapamiento"

### Paso 2: Ajustar el Porcentaje
- **Opción A:** Usa el **slider** (deslizador) para ajustar rápidamente
- **Opción B:** Ingresa el valor **exacto** en el campo numérico
- El **badge de color** cambia según el valor:
  - 🔵 **0%**: Gris (sin solapamiento)
  - 🔵 **1-25%**: Azul claro (bajo)
  - 🔵 **26-50%**: Azul (medio)
  - 🟡 **51-75%**: Amarillo (alto)
  - 🔴 **76-100%**: Rojo (muy alto)

### Paso 3: Guardar
1. Haz clic en **"Guardar"**
2. Verás una notificación de éxito
3. Haz clic en **"EJECUTAR Gantt"** para aplicar los cambios

## 📊 Guía de Valores (Incluida en el Modal)

El modal incluye una guía rápida:
- **0%**: Espera al 100% (comportamiento tradicional)
- **25%**: Procesos cortos o automáticos
- **50%**: Procesos manuales medianos
- **75%**: Procesos largos o críticos

## 🎨 Características de la Interfaz

### Modal Inteligente
- **Información de la tarea**: Muestra ID, Proyecto y Máquina
- **Slider sincronizado**: El slider y el campo numérico están sincronizados
- **Validación automática**: Solo acepta valores entre 0-100
- **Colores dinámicos**: El badge cambia de color según el porcentaje

### Notificaciones
- **Toast de éxito**: Aparece en la esquina superior derecha
- **Desaparece automáticamente**: Después de 5 segundos
- **Recordatorio**: Te indica que debes ejecutar el Gantt nuevamente

## 🔧 Funcionalidades Técnicas

### Clic Derecho
- **Previene el menú contextual** del navegador
- **Extrae automáticamente** la información de la tarea
- **Carga el valor actual** (si existe)

### Sincronización
- **Slider ↔ Input**: Ambos controles están sincronizados
- **Actualización en tiempo real**: El badge se actualiza instantáneamente

### API Integration
- **Endpoint**: `/api/update_overlap_percentage/`
- **Método**: POST
- **Validación**: Servidor valida el rango 0-100

## 📝 Ejemplo de Uso

### Escenario: Configurar Tarea 2654 (VF2, 100 horas)

1. **Clic derecho** en la tarea 2654
2. **Modal muestra**:
   ```
   ID: 2654
   Proyecto: S15-041
   Máquina: VF2
   ```
3. **Ajustar slider** a 75%
4. **Badge muestra**: 🔴 75% (color rojo)
5. **Guardar**
6. **Notificación**: "Solapamiento de 75% configurado para tarea 2654"
7. **Ejecutar Gantt** para ver el resultado

## ⚙️ Configuración Avanzada

### Valores Predeterminados
- **Sin configuración previa**: El modal muestra 0%
- **Con configuración previa**: (Próximamente) Cargará el valor guardado

### Persistencia
- Los valores se guardan en la base de datos (`prioridad_manual`)
- Permanecen hasta que los cambies manualmente
- Se aplican cada vez que ejecutas el Gantt

## 🐛 Solución de Problemas

### "El modal no aparece"
- Verifica que estés haciendo clic derecho en una **tarea** (no en el fondo)
- Asegúrate de que la tarea tenga el atributo `data-task-id`

### "Los cambios no se aplican"
- Debes hacer clic en **"EJECUTAR Gantt"** después de guardar
- Los cambios solo se aplican en la próxima ejecución

### "Error al guardar"
- Verifica que el servidor esté corriendo
- Revisa la consola del navegador (F12) para errores
- Verifica que la API esté configurada correctamente

## 🚀 Próximas Mejoras

- [ ] Cargar valor actual desde la base de datos
- [ ] Mostrar porcentaje en el tooltip de la tarea
- [ ] Configuración masiva (múltiples tareas a la vez)
- [ ] Presets rápidos (botones 0%, 25%, 50%, 75%)
- [ ] Historial de cambios

## 📞 Soporte

Si tienes problemas:
1. Revisa la consola del navegador (F12)
2. Verifica los logs del servidor Django
3. Consulta `SOLAPAMIENTO_README.md` para detalles técnicos

---

**¡Disfruta de la nueva funcionalidad!** 🎉
