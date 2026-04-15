
import sys

file_path = "produccion/templates/produccion/planificacion_visual.html"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

target = 'title="Toggle Tooltips">\n                          <i class="fas fa-comment text-primary"></i>\n                      </button>'
# Use a more robust search if that fails
if target not in content:
    # Try just the id
    target = 'id="btn-toggle-tooltips"'

insertion = """
                      <button id="btn-filter-ops" 
                              class="btn-modern glass rounded-pill px-2" 
                              style="height: 34px; border-color: #e2e8f0; color: #475569;" 
                              onclick="window.toggleOpFilterSidebar()" 
                              title="Filtrar Visibilidad de OPs">
                          <i class="fas fa-filter" style="color: #06b6d4;"></i>
                      </button>"""

if 'id="btn-filter-ops"' not in content:
    new_content = content.replace('id="btn-toggle-tooltips"', 'id="btn-toggle-tooltips"') # trigger?
    # Let's just find the closing tag of that button
    tag = 'id="btn-toggle-tooltips"'
    start = content.find(tag)
    if start != -1:
        end_button = content.find('</button>', start) + 9
        content = content[:end_button] + insertion + content[end_button:]
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("Success")
    else:
        print("Target not found")
else:
    print("Already exists")
