import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from django.test import RequestFactory
from produccion.ai_chat import ai_chat_command

rf = RequestFactory()
data = {'message': 'hola', 'scenario_id': None}
request = rf.post('/planificacion/visual/ai-chat/', data=json.dumps(data), content_type='application/json')

try:
    response = ai_chat_command(request)
    print("STATUS:", response.status_code)
    print("CONTENT:", response.content.decode('utf-8'))
except Exception as e:
    import traceback
    print("ERROR:", str(e))
    traceback.print_exc()
