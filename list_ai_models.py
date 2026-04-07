import os
import django
import json
import google.generativeai as genai

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from django.conf import settings

genai.configure(api_key=settings.GOOGLE_API_KEY)
try:
    print("Listing models:")
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(m.name)
except Exception as e:
    print("Error listing models:", str(e))
