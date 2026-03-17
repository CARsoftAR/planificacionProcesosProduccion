import json
from openai import OpenAI
from django.conf import settings
from .gantt_logic import get_gantt_data

def get_ai_planning_suggestion(request):
    """
    Takes current production state and sends it to OpenAI to get an optimized sequence.
    """
    # 1. Get current data (the same used for the Gantt)
    data = get_gantt_data(request, force_run=True)
    
    timeline_data = data['timeline_data']
    analysis = data['analysis']
    
    # 2. Simplify data for the AI (to reduce tokens and focus on scheduling)
    machines_context = []
    for row in timeline_data:
        m = row['machine']
        tasks = []
        for t in row['tasks']:
            tasks.append({
                'id_orden': t.get('Idorden'),
                'proyecto': t.get('ProyectoCode'),
                'descripcion': t.get('Descri'),
                'tiempo_horas': t.get('Tiempo_Proceso'),
                'vto_proyecto': str(t.get('Vto_Proyecto')),
                'prioridad_actual': t.get('OrdenVisual')
            })
        
        machines_context.append({
            'maquina_id': m.id_maquina,
            'nombre': m.nombre,
            'tareas_actuales': tasks
        })

    # 3. Prepare the Prompt
    prompt = f"""
    Eres un experto en planificación de producción industrial. Tu objetivo es optimizar la secuencia de trabajo de una fábrica metalúrgica.
    
    ESTADO ACTUAL DE LA FÁBRICA:
    {json.dumps(machines_context, indent=2)}
    
    ALERTAS DE RETRASO ACTUALES:
    {json.dumps(analysis.get('project_alerts', []), indent=2, default=str)}
    
    REGLAS DE NEGOCIO:
    1. Minimizar los retrasos respecto a la fecha de vencimiento (vto_proyecto).
    2. Agrupar tareas del mismo 'proyecto' en la misma máquina si es eficiente para reducir set-ups.
    3. Si una máquina está muy cargada y otra libre, sugerir mover tareas si son compatibles.
    
    TAREA:
    Devuelve un JSON con una lista de sugerencias de "reordenamiento". 
    Para cada tarea que deba cambiar, indica:
    - id_orden
    - nueva_prioridad (un número float, ej: 1500.0)
    - nueva_maquina_id (opcional, solo si sugieres moverla de máquina)
    - razon (breve explicación de por qué este cambio optimiza la producción)
    
    FORMATO DE RESPUESTA:
    Solo devuelve el JSON, sin texto explicativo adicional.
    {{
      "sugerencias": [
        {{ "id_orden": 12345, "nueva_prioridad": 1000.0, "razon": "Priorizar proyecto con vencimiento próximo" }},
        ...
      ]
    }}
    """

    # 4. Call OpenAI (via Opencode Zen)
    client = OpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url="https://opencode.ai/zen/v1"
    )
    
    try:
        response = client.chat.completions.create(
            model="big-pickle", 
            messages=[
                {"role": "system", "content": "Eres un asistente de planificación de producción. Responde siempre en formato JSON puro."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1 # More deterministic for planning
        )
        
        content = response.choices[0].message.content
        if not content:
            return {"error": "El servidor de IA devolvió una respuesta vacía."}

        # More robust JSON extraction
        import re
        json_match = re.search(r'(\{.*\}|\[.*\])', content, re.DOTALL)
        if json_match:
            clean_content = json_match.group(0)
        else:
            clean_content = content.strip()
            
        try:
            ai_response = json.loads(clean_content)
            return ai_response
        except json.JSONDecodeError as je:
            return {
                "error": f"La IA no devolvió un JSON válido. Respuesta: {content[:200]}...",
                "raw_response": content
            }

    except Exception as e:
        # Avoid character map errors in terminal by not printing the whole exception if it contains weird chars
        # But we still want to log it for the developer
        return {"error": f"Error al procesar respuesta de IA: {str(e)}"}
