# Sistema de Solapamiento de Procesos

## 📋 Descripción

El sistema ahora soporta **solapamiento inteligente** entre procesos dependientes, permitiendo que un proceso sucesor inicie antes de que termine completamente el proceso predecesor, minimizando tiempos muertos y optimizando el flujo de producción.

## 🎯 Problema que Resuelve

### Situación SIN Solapamiento:
```
Proceso 1 (Máquina A): [████████████████████] 5h → 20 piezas
                                              ↓ (espera 100%)
Proceso 2 (Máquina B):                        [████████] 2h
                                              
Tiempo total: 7 horas
Máquina B ociosa: 5 horas ❌
```

### Situación CON Solapamiento Óptimo:
```
Proceso 1 (Máquina A): [████████████████████] 5h → 20 piezas
                           ↓ (inicia con 50% listo)
Proceso 2 (Máquina B):     [████████] 2h
                           
Tiempo total: 5 horas (mismo que Proceso 1)
Máquina B ociosa: 0 horas ✅
Ahorro: 2 horas
```

## 🔧 Cómo Usar

### 1. Configurar Porcentaje de Solapamiento

En la interfaz de planificación visual, para cada tarea puedes configurar:

- **% Solapamiento**: Porcentaje del lote del proceso predecesor que debe estar completo antes de iniciar
  - `0%` = Espera al 100% (comportamiento tradicional)
  - `25%` = Inicia cuando el predecesor lleva 25% completado
  - `50%` = Inicia cuando el predecesor lleva 50% completado
  - `100%` = Intenta iniciar lo antes posible (apenas haya 1 pieza)

### 2. El Sistema Calcula Automáticamente

El algoritmo determina el **momento óptimo** de inicio considerando:

1. **Lote Mínimo**: ¿Cuántas piezas necesita el sucesor para arrancar?
2. **Tasas de Producción**: ¿Qué tan rápido produce cada proceso?
3. **Sincronización**: Evita que el sucesor termine antes y quede esperando

## 📊 Estrategias de Cálculo

### Estrategia 1: INICIO_TEMPRANO
**Cuándo:** El sucesor es MÁS LENTO que el predecesor

```
Predecesor: 0.25h/pieza
Sucesor:    0.50h/pieza (MÁS LENTO)

Resultado: Inicia apenas tenga el lote mínimo
Razón: No hay riesgo de tiempo muerto (el predecesor siempre va adelante)
```

### Estrategia 2: INICIO_SINCRONIZADO
**Cuándo:** El sucesor es MÁS RÁPIDO que el predecesor

```
Predecesor: 0.25h/pieza
Sucesor:    0.10h/pieza (MÁS RÁPIDO)

Resultado: Calcula inicio para terminar justo cuando termine el predecesor
Razón: Evita tiempo muerto esperando las últimas piezas
```

### Estrategia 3: INICIO_MINIMO
**Cuándo:** El inicio calculado requiere más piezas que el lote mínimo configurado

```
Lote mínimo configurado: 50%
Inicio óptimo requiere: 60%

Resultado: Inicia con el 50% (respeta configuración del usuario)
Razón: Prioriza la configuración manual sobre la optimización automática
```

## 💡 Ejemplo Práctico

### Datos:
- **Proceso 3** (Máquina 1): 20 piezas en 5 horas
- **Proceso 2** (Máquina 5): 20 piezas en 1 hora
- **Configuración**: 50% de solapamiento

### Cálculo:
```
Tasa Proceso 3: 5h ÷ 20 = 0.25h/pieza
Tasa Proceso 2: 1h ÷ 20 = 0.05h/pieza (¡5x MÁS RÁPIDO!)

Lote mínimo: 20 × 50% = 10 piezas
Tiempo para 10 piezas: 0.25h × 10 = 2.5 horas

Inicio calculado para sincronización:
  Fin P3 - Duración P2 = 12:00 - 1h = 11:00

Verificación:
  A las 11:00, P3 lleva: (11:00 - 07:00) ÷ 0.25 = 16 piezas ✅
  16 piezas > 10 piezas mínimas ✅

Resultado: Proceso 2 inicia a las 11:00
Estrategia: INICIO_SINCRONIZADO
Tiempo muerto: 0 horas ✅
```

## 📈 Beneficios

1. **Reducción de Tiempos Muertos**: Las máquinas no esperan innecesariamente
2. **Mejor Utilización**: Máquinas trabajan más tiempo productivo
3. **Flexibilidad**: Configurable por tarea según necesidades
4. **Automático**: El sistema calcula el mejor momento de inicio
5. **Seguro**: Respeta restricciones de lote mínimo

## ⚙️ Configuración en Base de Datos

El porcentaje se guarda en la tabla `prioridad_manual`:

```sql
UPDATE prioridad_manual 
SET porcentaje_solapamiento = 50.0 
WHERE id_orden = 12345;
```

## 🔍 Monitoreo

Durante la ejecución, el sistema muestra en consola:

```
✅ Task 46540: Optimal overlap at 50% (INICIO_SINCRONIZADO)
⚠️  Task 46538: 1.5h idle time (strategy: INICIO_TEMPRANO)
```

## ⚠️ Consideraciones

1. **Primera Ejecución**: El solapamiento se aplica desde el segundo pase (necesita info de timing)
2. **Dependencias Múltiples**: Si hay varios predecesores, usa el más restrictivo
3. **Horarios**: El cálculo respeta horarios de máquinas y feriados
4. **Validación**: El sistema verifica que haya suficientes piezas disponibles

## 🎓 Mejores Prácticas

1. **Procesos Manuales**: Usa solapamiento alto (50-75%)
2. **Procesos Automáticos**: Usa solapamiento bajo (0-25%) o ninguno
3. **Lotes Grandes**: Más margen para solapamiento
4. **Lotes Pequeños**: Solapamiento bajo o nulo
5. **Prueba Gradual**: Empieza con 25% y ajusta según resultados

## 📞 Soporte

Si tienes dudas sobre qué porcentaje usar para un proceso específico, considera:
- ¿El proceso puede trabajar con piezas parciales?
- ¿Qué tan crítico es el tiempo de entrega?
- ¿Hay riesgo de retrabajo si se inicia muy temprano?

---

**Versión**: 1.0  
**Fecha**: Diciembre 2025  
**Módulo**: `overlap_calculator.py` + `gantt_logic.py`
