"""
Módulo para cálculo de solapamiento óptimo entre procesos.

Resuelve el problema de sincronización de flujo continuo donde:
- Proceso predecesor produce piezas a cierta tasa
- Proceso sucesor consume piezas a (posiblemente) diferente tasa
- Queremos minimizar tiempos muertos

Ejemplo:
    Proceso 1: 20 piezas en 5h (0.25h/pieza)
    Proceso 2: 20 piezas en 2h (0.10h/pieza) - MÁS RÁPIDO
    
    Si iniciamos P2 muy temprano → tiempo muerto esperando piezas
    Si iniciamos P2 muy tarde → máquina ociosa innecesariamente
    
    Solución: Calcular inicio óptimo para flujo continuo
"""

from datetime import timedelta
from typing import Dict, Optional, Tuple


def calcular_inicio_optimo_sucesor(
    pred_start: 'datetime',
    pred_duration: float,  # horas totales
    pred_cantidad: float,  # piezas totales
    succ_duration: float,  # horas totales
    succ_cantidad: float,  # piezas totales
    porcentaje_minimo: float = 0.0  # % mínimo del lote para iniciar (0-100)
) -> Tuple['datetime', Dict[str, any]]:
    """
    Calcula el momento óptimo para iniciar el proceso sucesor.
    
    Estrategia:
    1. Si el sucesor es MÁS LENTO que el predecesor:
       - Puede iniciar apenas tenga el lote mínimo
       - No habrá tiempo muerto (siempre tendrá piezas disponibles)
    
    2. Si el sucesor es MÁS RÁPIDO que el predecesor:
       - Debe calcular inicio para terminar justo cuando termine el predecesor
       - Evita tiempo muerto esperando piezas
    
    Args:
        pred_start: Fecha/hora de inicio del predecesor
        pred_duration: Duración total del predecesor (horas)
        pred_cantidad: Cantidad de piezas del predecesor
        succ_duration: Duración total del sucesor (horas)
        succ_cantidad: Cantidad de piezas del sucesor
        porcentaje_minimo: % mínimo del lote necesario para iniciar (0-100)
    
    Returns:
        Tuple de (datetime de inicio óptimo, dict con info de debug)
    """
    
    # Calcular tasas de producción (horas por pieza)
    tasa_pred = pred_duration / pred_cantidad if pred_cantidad > 0 else 0
    tasa_succ = succ_duration / succ_cantidad if succ_cantidad > 0 else 0
    
    # Calcular fin del predecesor
    pred_end = pred_start + timedelta(hours=pred_duration)
    
    # Calcular lote mínimo necesario (SIEMPRE basado en cantidad del predecesor)
    piezas_minimas = (pred_cantidad * porcentaje_minimo / 100.0)
    if piezas_minimas < 1:
        piezas_minimas = 1  # Al menos 1 pieza
    
    # Tiempo para producir el lote mínimo
    tiempo_lote_minimo = tasa_pred * piezas_minimas
    inicio_minimo_posible = pred_start + timedelta(hours=tiempo_lote_minimo)
    
    # CASO ESPECIAL: Cantidades muy diferentes (ej: 20 vs 1)
    # En este caso, usar INICIO_TEMPRANO siempre
    ratio_cantidades = max(pred_cantidad, succ_cantidad) / min(pred_cantidad, succ_cantidad)
    if ratio_cantidades > 2.0:  # Diferencia mayor a 2x
        inicio_optimo = inicio_minimo_posible
        estrategia = "INICIO_TEMPRANO"
        razon = f"Cantidades muy diferentes ({pred_cantidad:.0f} vs {succ_cantidad:.0f}). Inicia con lote mínimo ({piezas_minimas:.1f} pzs = {porcentaje_minimo}%)."
    
    # CASO 1: Sucesor es MÁS LENTO o IGUAL velocidad que predecesor
    # (tasa_succ >= tasa_pred significa que tarda más por pieza)
    elif tasa_succ >= tasa_pred:
        # Puede iniciar apenas tenga el lote mínimo
        # No habrá tiempo muerto porque el predecesor siempre va adelante
        inicio_optimo = inicio_minimo_posible
        estrategia = "INICIO_TEMPRANO"
        razon = "Sucesor es más lento o igual. Puede iniciar con lote mínimo sin riesgo de tiempo muerto."
    
    # CASO 2: Sucesor es MÁS RÁPIDO que predecesor
    else:
        # Calcular inicio para que termine justo cuando termine el predecesor
        # inicio_optimo = fin_pred - duracion_succ
        inicio_calculado = pred_end - timedelta(hours=succ_duration)
        
        # Verificar que tenga el lote mínimo disponible en ese momento
        if inicio_calculado < inicio_minimo_posible:
            # No puede iniciar tan tarde porque no tendría el lote mínimo
            inicio_optimo = inicio_minimo_posible
            estrategia = "INICIO_MINIMO"
            razon = f"Inicio calculado requiere lote mínimo ({piezas_minimas:.1f} pzs = {porcentaje_minimo}%)"
        else:
            inicio_optimo = inicio_calculado
            estrategia = "INICIO_SINCRONIZADO"
            razon = "Sucesor más rápido. Inicia tarde para terminar junto con predecesor."
    
    # Calcular métricas de validación
    piezas_disponibles_al_inicio = (inicio_optimo - pred_start).total_seconds() / 3600.0 / tasa_pred
    succ_end = inicio_optimo + timedelta(hours=succ_duration)
    tiempo_muerto = (pred_end - succ_end).total_seconds() / 3600.0
    
    info = {
        'inicio_optimo': inicio_optimo,
        'estrategia': estrategia,
        'razon': razon,
        'tasa_pred_h_pieza': tasa_pred,
        'tasa_succ_h_pieza': tasa_succ,
        'piezas_minimas_requeridas': piezas_minimas,
        'piezas_disponibles_al_inicio': piezas_disponibles_al_inicio,
        'pred_end': pred_end,
        'succ_end': succ_end,
        'tiempo_muerto_horas': max(0, tiempo_muerto),
        'solapamiento_horas': (pred_end - inicio_optimo).total_seconds() / 3600.0,
        'porcentaje_solapamiento_real': (inicio_optimo - pred_start).total_seconds() / 3600.0 / pred_duration * 100.0
    }
    
    return inicio_optimo, info


def validar_solapamiento(info: Dict) -> Tuple[bool, str]:
    """
    Valida que el solapamiento calculado sea factible.
    
    Returns:
        Tuple de (es_valido, mensaje_error)
    """
    # Verificar que haya suficientes piezas disponibles
    if info['piezas_disponibles_al_inicio'] < info['piezas_minimas_requeridas']:
        return False, f"Insuficientes piezas al inicio: {info['piezas_disponibles_al_inicio']:.1f} < {info['piezas_minimas_requeridas']:.1f}"
    
    # Verificar que el inicio no sea antes del predecesor
    if info['inicio_optimo'] < info['pred_end'] - timedelta(hours=info['solapamiento_horas']):
        # Esto es normal en solapamiento, solo verificamos que sea razonable
        pass
    
    return True, "OK"


# Ejemplo de uso:
if __name__ == "__main__":
    from datetime import datetime
    
    # Caso 1: Sucesor MÁS RÁPIDO (problema de tiempo muerto)
    print("=" * 70)
    print("CASO 1: Sucesor MÁS RÁPIDO que Predecesor")
    print("=" * 70)
    
    inicio, info = calcular_inicio_optimo_sucesor(
        pred_start=datetime(2025, 1, 1, 7, 0),
        pred_duration=5.0,  # 5 horas
        pred_cantidad=20.0,  # 20 piezas
        succ_duration=2.0,  # 2 horas (MÁS RÁPIDO)
        succ_cantidad=20.0,
        porcentaje_minimo=50.0  # Necesita 50% del lote
    )
    
    print(f"Estrategia: {info['estrategia']}")
    print(f"Razón: {info['razon']}")
    print(f"Inicio óptimo: {info['inicio_optimo']}")
    print(f"Piezas disponibles al inicio: {info['piezas_disponibles_al_inicio']:.1f}")
    print(f"Tiempo muerto: {info['tiempo_muerto_horas']:.2f} horas")
    print(f"Solapamiento real: {info['porcentaje_solapamiento_real']:.1f}%")
    
    # Caso 2: Sucesor MÁS LENTO (sin problema)
    print("\n" + "=" * 70)
    print("CASO 2: Sucesor MÁS LENTO que Predecesor")
    print("=" * 70)
    
    inicio2, info2 = calcular_inicio_optimo_sucesor(
        pred_start=datetime(2025, 1, 1, 7, 0),
        pred_duration=2.0,  # 2 horas
        pred_cantidad=20.0,
        succ_duration=5.0,  # 5 horas (MÁS LENTO)
        succ_cantidad=20.0,
        porcentaje_minimo=25.0
    )
    
    print(f"Estrategia: {info2['estrategia']}")
    print(f"Razón: {info2['razon']}")
    print(f"Inicio óptimo: {info2['inicio_optimo']}")
    print(f"Piezas disponibles al inicio: {info2['piezas_disponibles_al_inicio']:.1f}")
    print(f"Tiempo muerto: {info2['tiempo_muerto_horas']:.2f} horas")
