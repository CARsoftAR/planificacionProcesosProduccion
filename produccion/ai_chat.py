import json
import traceback
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import google.generativeai as genai
from .models import MaquinaConfig

@csrf_exempt
def ai_chat_command(request):
    """
    Recibe comandos en lenguaje natural del usuario, usa Gemini para extraer variables,
    y ejecuta acciones sobre el sistema (como redireccionamientos, pins, etc.).
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido. Usa POST.'}, status=405)

    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        scenario_id = data.get('scenario_id', None)

        if not user_message:
            return JsonResponse({'success': False, 'error': 'El mensaje está vacío.'})

        if not hasattr(settings, 'GOOGLE_API_KEY') or not settings.GOOGLE_API_KEY:
             return JsonResponse({'success': False, 'error': 'La API Key de Google no está configurada.'})

        # Configurar Gemini
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        model = genai.GenerativeModel("gemini-flash-latest")


        # Obtener lista de máquinas para darle contexto a la IA
        maquinas = list(MaquinaConfig.objects.using('default').values_list('nombre', 'id_maquina'))
        maquinas_context = "\n".join([f"- Nombre común: {m[0]}, ID exacto: {m[1]}" for m in maquinas])

        prompt = f"""
Eres un asistente experto del sistema de planificación industrial "CARsoftAR".
Tu trabajo es interpretar la orden del operario en lenguaje natural (Español) y devolver ÚNICAMENTE un objeto JSON válido con la configuración de la acción que debe tomar el sistema. NO uses bloques de código (```json), solo devuelve el texto plano del JSON.

REGLAS CRÍTICAS:
1. USA ÚNICAMENTE los 'ID exacto' proporcionados en la lista de abajo para completar los campos. Jamás adivines un ID.
2. Si el usuario dice "Haas", busca la coincidencia más exacta. Si hay "HAAS" (MAC08) y "HAAS MILL ME048" (MAC43), y el usuario solo dice "Haas", prioriza la que es exactamente "HAAS" (MAC08).
3. NO generes Markdown, solo texto JSON puro.

Intenciones (intent) disponibles en este momento:
1. "REDISTRIBUIR_FALLA": El operario quiere mover las órdenes de producción de una máquina origen hacia una máquina destino compatible. Ya NO es necesario que haya una falla activa; puede usarse para balancear carga de trabajo.
2. "UNKNOWN": Si la orden del usuario no se parece a nada que sepas hacer, o hace una pregunta general.

Si la intención es "REDISTRIBUIR_FALLA", el JSON DEBE tener esta estructura:
{{
  "intent": "REDISTRIBUIR_FALLA",
  "from_machine_id": "<ID exacto de la máquina origen según la lista>",
  "to_machine_id": "<ID exacto de la máquina destino según la lista>",
  "message": "He detectado tu orden de redistribuir tareas desde [Nombre Origen] hacia [Nombre Destino], aplicando factores de eficiencia si existen..."
}}

Si la intención es "UNKNOWN", el JSON DEBE tener:
{{
  "intent": "UNKNOWN",
  "message": "Lo siento, por ahora solo puedo ayudarte a redistribuir tareas entre máquinas para balancear carga o por falla técnica. ¿Qué máquina quieres descargar?"
}}

---
LISTA DE MÁQUINAS (Usa SOLO los 'ID exacto' para los campos _id):
{maquinas_context}

---
Mensaje del Operario: "{user_message}"
        """

        # Llamar a Gemini
        response = model.generate_content(prompt)
        text_response = response.text.strip()
        
        # LOG PARA DEPURACIÓN: Ver qué respondió la IA en la consola del servidor
        print(f"=== AI CHAT DEBUG: Gemini Response ===\n{{text_response}}\n======================================")
        
        # Limpiar bloques de código si Gemini los mandó por error
        if text_response.startswith('```json'):
            text_response = text_response[7:]
        if text_response.startswith('```'):
            text_response = text_response[3:]
        if text_response.endswith('```'):
            text_response = text_response[:-3]
            
        try:
            parsed_command = json.loads(text_response.strip())
        except json.JSONDecodeError:
            print("=== RAW GEMINI ERROR ===")
            print(text_response)
            return JsonResponse({'success': False, 'error': 'La inteligencia artificial devolvió una respuesta que no se pudo procesar automáticamente.'})

        intent = parsed_command.get('intent', 'UNKNOWN')

        if intent == 'UNKNOWN':
            return JsonResponse({'success': True, 'action': 'chat', 'message': parsed_command.get('message', 'No entendí la orden.')})

        elif intent == 'REDISTRIBUIR_FALLA':
            # Ejecutar la lógica de redistribución (re-usamos el endpoint a través de una llamada directa)
            from_m = parsed_command.get('from_machine_id')
            to_m = parsed_command.get('to_machine_id')
            
            if not from_m or not to_m:
                return JsonResponse({'success': False, 'error': 'La IA no pudo identificar correctamente las máquinas.'})

            # Import views directly here to avoid circular dependencies
            from . import views
            from django.test import RequestFactory
            
            # Simulated GET request for the existing view
            rf = RequestFactory()
            get_params = {'from': from_m, 'to': to_m}
            if scenario_id:
                 get_params['scenario_id'] = str(scenario_id)
                 
            # Note: We need projects... If the user is viewing filtered projects, the AI won't know unless we pass it.
            # But the 'redistribute_tasks' view scans the gantt. We'll pass an empty string so it loads everything.
            get_params['proyectos'] = request.GET.get('proyectos', '')
            
            fake_request = rf.get('/api/redistribute_tasks/', get_params)
            
            # Llama a la vista existente
            redistribute_response = views.redistribute_tasks(fake_request)
            red_data = json.loads(redistribute_response.content)
            
            if red_data.get('success'):
                count = red_data.get('moved_count', 0)
                msg = f"¡Listo! La inteligencia artificial redistribuyó exitosamente {count} tareas desde {from_m} hacia {to_m}. (Se actualizará el Gantt)." if count > 0 else f"No se encontraron tareas afectadas en {from_m} para mover a {to_m}."
                return JsonResponse({
                    'success': True,
                    'action': 'refresh',
                    'message': msg
                })
            else:
                 error_msg = red_data.get('error', 'Error desconocido en la vista interna.')
                 return JsonResponse({'success': False, 'error': f"Hubo un error al mover internamente: {error_msg}"})
        
        return JsonResponse({'success': False, 'error': 'Comando procesado pero no implementado.'})

    except Exception as e:
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'error': f'Error del servidor IA: {str(e)}'})
