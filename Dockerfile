# Alap kép: Python 3.9
FROM python:3.9-slim

# Mappa létrehozása az alkalmazáshoz
WORKDIR /app

# Másold a requirements.txt fájlt az image-be
COPY requirements.txt .

# Függőségek telepítése
RUN pip install --no-cache-dir -r requirements.txt

# Másold az összes alkalmazásfájlt az image-be
COPY . .

# Indítsd el a Flask alkalmazást
CMD ["python", "servicenow6.py"]

# Port megnyitása
EXPOSE 5000
