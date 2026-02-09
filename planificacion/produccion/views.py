from django.shortcuts import render
from django.http import JsonResponse
from .services import get_planificacion_data

def planificacion_list(request):
    """
    Vista principal para listar la planificación.
    Acepta parámetros GET para filtrar.
    """
    # Extraer filtros del request
    filtros = {}
    
    # Ejemplo: ?orden=12345
    orden = request.GET.get('orden')
    if orden:
        filtros['id_orden'] = orden
        
    # Ejemplo: ?proyectos=1001,1002
    proyectos = request.GET.get('proyectos')
    if proyectos:
        filtros['proyectos'] = proyectos.split(',')

    try:
        data = get_planificacion_data(filtros)
        return JsonResponse({'data': data}, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
