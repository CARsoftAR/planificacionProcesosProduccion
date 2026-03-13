from produccion.services import get_planificacion_data
from collections import Counter

data = get_planificacion_data({}) # Fetch all
counts = Counter(str(t.get('Idmaquina', '')).strip() for t in data)
print("MACHINE CODES (Idmaquina):")
for code, count in counts.items():
    print(f" - '{code}': {count} tasks")

counts_d = Counter(str(t.get('MAQUINAD', '')).strip() for t in data)
print("\nMACHINE NAMES (MAQUINAD):")
for name, count in counts_d.items():
    print(f" - '{name}': {count} tasks")
