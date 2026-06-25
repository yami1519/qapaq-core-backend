Para levantar el Core 
# 1. Salir del venv roto
deactivate

# 2. Borrar el venv viejo
rm -rf venv

# 3. Verificar que Python responda (usa 3.12)
python --version

# 4. Crear el venv nuevo y limpio
py -3.12 -m venv venv

# 5. Activar
source venv/Scripts/activate

# 6. Confirmar que apunta al venv correcto
which python
# debe terminar en: web_banck_core_andino_fastapi/venv/Scripts/python

# 7. Instalar dependencias
pip install -r requirements.txt

# 8. Levantar
uvicorn main:app --reload --port 8001