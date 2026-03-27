# ⚡ Affiliate Intelligence

Analizador de potencial para marketing de afiliados con **datos reales** de:
- 📈 Google Trends RSS (tendencias por país)
- 📚 Wikipedia Pageviews API (demanda real)
- 🔍 Google Autocomplete (competencia)
- 🧮 Estimador de márgenes por tipo de producto

## Estructura
```
affiliate-app/
├── app.py              ← Backend Flask (APIs + lógica)
├── templates/
│   └── index.html      ← Frontend completo
├── requirements.txt
├── Procfile            ← Para Railway
└── render.yaml         ← Para Render.com
```

---

## 🚀 Opción 1: Render.com (GRATIS, recomendado)

1. Crea cuenta en https://render.com
2. Conecta tu GitHub: sube esta carpeta como repositorio
3. Crea nuevo "Web Service" → selecciona el repo
4. Render detecta `render.yaml` automáticamente
5. Deploy → en 2 minutos tienes tu URL pública

---

## 🚀 Opción 2: Railway.app (GRATIS con límites)

1. Crea cuenta en https://railway.app
2. "New Project" → "Deploy from GitHub repo"
3. Sube la carpeta como repo en GitHub
4. Railway detecta el `Procfile` automáticamente
5. Deploy listo en ~1 minuto

---

## 💻 Correr localmente

```bash
cd affiliate-app
pip install -r requirements.txt
python app.py
# Abre http://localhost:5000
```

---

## 🔧 Agregar más fuentes de datos (futuro)

Para agregar APIs de pago cuando quieras escalar:

| API | Para qué | Costo |
|-----|----------|-------|
| SerpApi | Google Trends real | $50/mes |
| DataForSEO | CPC + volumen keywords | $50/mes |
| Semrush API | Competencia SEO | $120/mes |

Solo agrega la API key en `app.py` y llama al endpoint correspondiente.
