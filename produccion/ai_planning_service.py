import json
import re
from datetime import timedelta
import google.generativeai as genai
from django.conf import settings
from .gantt_logic import get_gantt_data

def get_ai_planning_suggestion(request):
    """
    Takes current production state and sends it to Google Gemini to get an optimized sequence.
    """
    # 1. Get current data
    data = get_gantt_data(request, force_run=True)
    
    timeline_data = data['timeline_data']
    analysis = data['analysis']
    start_simulation = data.get('start_simulation')
    
    # 2. Preparation for Gemini (15 days lookahead)
    cut_off_date = start_simulation + timedelta(days=15)
    
    machines_context = []
    active_projects = set()
    
    for row in timeline_data:
        m = row['machine']
        tasks = []
        for t in row['tasks']:
            t_start = t.get('start_date')
            if t_start and t_start > cut_off_date:
                continue
                
            active_projects.add(t.get('ProyectoCode'))
            tasks.append({
                'id': t.get('Idorden'),
                'prj': t.get('ProyectoCode'),
                'dsc': str(t.get('Descri'))[:30],
                'hs': t.get('Tiempo_Proceso'),
                'vto': str(t.get('Vto_Proyecto')),
                'p_act': t.get('OrdenVisual')
            })
        
        if tasks:
            machines_context.append({
                'm_id': m.id_maquina,
                'm_nom': m.nombre,
                'tasks': tasks
            })

    simple_alerts = []
    for alert in analysis.get('project_alerts', []):
        prj = alert.get('project')
        if prj in active_projects:
            simple_alerts.append({
                'proyecto': prj,
                'retraso_horas': alert.get('delay_hours')
            })

    # 3. Comprehensive Prompt
    prompt = f"""
    Eres un experto en planificación industrial (Metalúrgica). 
    Tu objetivo es REORDENAR las tareas para minimizar los retrasos respecto a la fecha de vencimiento (vto).
    
    REGLAS:
    1. Agrupar tareas del mismo proyecto en la misma máquina para ahorrar tiempos de preparación.
    2. Priorizar tareas de proyectos con retrasos críticos en ALERTAS.
    3. Balancear la carga entre máquinas si alguna está libre.
    
    ESTADO DE LA FÁBRICA:
    {json.dumps(machines_context, indent=2)}
    
    ALERTAS DE RETRASO:
    {json.dumps(simple_alerts, indent=2)}
    
    TAREA:
    Responde ÚNICAMENTE en formato JSON con una lista de sugerencias.
    Para cada cambio indica:
    - id_orden (el id original)
    - nueva_prioridad (un número float, ej: 1500.0)
    - razon (una explicación breve en español)
    
    EJEMPLO DE RESPUESTA:
    {{
      "sugerencias": [
        {{ "id_orden": 12345, "nueva_prioridad": 500.0, "razon": "Priorizar proyecto urgente" }}
      ]
    }}
    """

    # 4. Call Google Gemini
    try:
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        # Using exact model name from list_models()
        model = genai.GenerativeModel('models/gemini-flash-latest')
        
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                response_mime_type="application/json"
            )
        )
        
        content = response.text
        if not content:
            return {"error": "La IA devolvió una respuesta vacía."}

        # Try to parse JSON directly
        try:
            ai_response = json.loads(content)
            return ai_response
        except json.JSONDecodeError:
            # Fallback re-search for JSON
            json_match = re.search(r'(\{.*\}|\[.*\])', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            return {"error": "Error al interpretar la respuesta de la IA."}

    except Exception as e:
        error_msg = str(e)
        friendly_msg = "Error al conectar con Gemini Directo."
        
        if "429" in error_msg:
            friendly_msg = "Se alcanzó el límite gratuito de Google. Espere un minuto."
        elif "API_KEY_INVALID" in error_msg or "403" in error_msg:
            friendly_msg = "La API Key de Google proporcionada no es válida o no tiene permisos."
            
        return {
            "error": friendly_msg,
            "technical_details": error_msg[:200]
        }
