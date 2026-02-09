# Guía Rápida: Configurar Solapamiento de Procesos

## 🚀 Cómo Usar el Sistema

### Paso 1: Ejecutar la Planificación

1. Ve a **Planificación Visual**
2. Haz clic en **"EJECUTAR Gantt"**
3. Espera a que se calculen las tareas

### Paso 2: Configurar Solapamiento

Hay **2 formas** de configurar el porcentaje de solapamiento:

#### Opción A: Desde la Interfaz Web (Próximamente)
- Haz clic derecho en una tarea
- Selecciona "Configurar Solapamiento"
- Ingresa el porcentaje (0-100)

#### Opción B: Desde la Base de Datos (Actual)

```python
# Abrir shell de Django
python manage.py shell

# Importar modelo
from produccion.models import PrioridadManual

# Configurar solapamiento para una tarea específica
tarea = PrioridadManual.objects.get_or_create(
    id_orden=46540,  # Reemplaza con tu ID de orden
    defaults={'maquina': 'VF2', 'prioridad': 1000}
)[0]

tarea.porcentaje_solapamiento = 50.0  # 50% de solapamiento
tarea.save()

print(f"✅ Configurado solapamiento de {tarea.porcentaje_solapamiento}% para tarea {tarea.id_orden}")
```

#### Opción C: SQL Directo

```sql
-- Actualizar solapamiento para una tarea
UPDATE prioridad_manual 
SET porcentaje_solapamiento = 50.0 
WHERE id_orden = 46540;

-- Insertar nueva configuración
INSERT INTO prioridad_manual (id_orden, maquina, prioridad, porcentaje_solapamiento)
VALUES (46540, 'VF2', 1000, 50.0);
```

### Paso 3: Ver Resultados

1. Vuelve a **"EJECUTAR Gantt"**
2. Observa la consola del servidor para ver los mensajes:
   ```
   ✅ Task 46540: Optimal overlap at 50% (INICIO_SINCRONIZADO)
   ```
3. Las tareas ahora iniciarán en el momento óptimo calculado

## 📊 Valores Recomendados

| Tipo de Proceso | % Recomendado | Razón |
|----------------|---------------|-------|
| **Manual con lotes grandes** | 50-75% | Puede trabajar con piezas parciales |
| **Manual con lotes pequeños** | 25-50% | Necesita más piezas para arrancar |
| **Automático** | 0-25% | Generalmente necesita lote completo |
| **Crítico/Urgente** | 75-100% | Minimiza tiempo total |
| **Sin restricciones** | 0% | Espera al 100% (comportamiento tradicional) |

## 🔍 Ejemplo Práctico

**Escenario:**
- Proyecto: 25-098
- Proceso 3 (HAAS): 20 piezas, 5 horas
- Proceso 2 (VF2): 20 piezas, 2 horas

**Sin Solapamiento (0%):**
```
HAAS: 07:00 ████████████████████ 12:00
VF2:                              12:00 ████ 14:00
```
Tiempo total: 7 horas

**Con Solapamiento (50%):**
```
HAAS: 07:00 ████████████████████ 12:00
VF2:              10:00 ████ 12:00
```
Tiempo total: 5 horas ✅ **Ahorro: 2 horas**

## 🛠️ Troubleshooting

### "No veo cambios después de configurar"
- Asegúrate de hacer clic en **"EJECUTAR Gantt"** nuevamente
- Verifica que el `id_orden` sea correcto

### "Aparece tiempo muerto"
- El sistema está calculando el inicio óptimo
- Si el sucesor es muy rápido, puede haber tiempo muerto inevitable
- Considera ajustar el porcentaje

### "No funciona el solapamiento"
- Verifica que haya dependencias entre las tareas
- Solo funciona si las tareas están en el mismo proyecto
- Revisa la consola del servidor para mensajes de error

## 📞 Próximos Pasos

1. **Prueba con una tarea**: Configura 50% en una tarea de prueba
2. **Observa resultados**: Revisa los logs en consola
3. **Ajusta según necesidad**: Incrementa o reduce el porcentaje
4. **Documenta tus hallazgos**: Anota qué porcentajes funcionan mejor para cada tipo de proceso

---

**¿Necesitas ayuda?** Revisa `SOLAPAMIENTO_README.md` para más detalles técnicos.
