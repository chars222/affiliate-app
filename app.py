from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import requests
import re
from urllib.parse import quote
import os
from dotenv import load_dotenv
import google.generativeai as genai

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
CORS(app)

# ==============================================================================
# 🔑 LLAVES DE APIs
# ==============================================================================
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "") 
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# NUEVA LLAVE: API de Scraping (Ej: RapidAPI)
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")

# Configurar el modelo de IA 
ai_model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        ai_model = genai.GenerativeModel('gemini-2.5-flash')
    except AttributeError as e:
        print(f"⚠️ ERROR DE VERSIÓN: {e}")
        print("=> Ejecuta en tu terminal: pip install --upgrade google-generativeai")
        ai_model = None

# ─── 1. EXTRACCIÓN CRUDA DE YOUTUBE CON ESTADÍSTICAS ──────────────────────────
def get_raw_youtube_comments(keyword, api_key=""):
    """Extrae comentarios reales ordenando por videos más populares (viewCount)."""
    if not api_key:
        return {"comments": [], "videos_count": 0, "comments_count": 0}
    
    try:
        # Forzamos a buscar los 5 videos más VISTOS (order=viewCount)
        search_url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={quote(keyword + ' curso OR negocio OR aprender')}&type=video&order=viewCount&maxResults=5&key={api_key}"
        search_resp = requests.get(search_url, timeout=8).json()
        
        if "items" not in search_resp:
            return {"comments": [], "videos_count": 0, "comments_count": 0}
            
        video_ids = [item["id"]["videoId"] for item in search_resp["items"]]
        all_comments = []
        
        for vid in video_ids:
            # Aumentamos a 25 comentarios extraídos por cada video popular
            comment_url = f"https://www.googleapis.com/youtube/v3/commentThreads?part=snippet&videoId={vid}&maxResults=25&key={api_key}"
            comment_resp = requests.get(comment_url, timeout=8).json()
            
            for item in comment_resp.get("items", []):
                text = item["snippet"]["topLevelComment"]["snippet"]["textOriginal"]
                all_comments.append(text)
                
        return {
            "comments": all_comments,
            "videos_count": len(video_ids),
            "comments_count": len(all_comments)
        }
    except Exception as e:
        print(f"Error YouTube: {e}")
        return {"comments": [], "videos_count": 0, "comments_count": 0}

# ─── 2. EL CEREBRO DE IA (MARKETER EXPERTO + META ESTIMADO) ───────────────────
def get_ai_insights(keyword, country, product_type, raw_comments):
    if not ai_model:
        return {
            "social_saturation_score": 50, "social_label": "Falta API Key",
            "meta_ads_score": 50, "meta_ads_label": "Falta API Key Gemini",
            "angles": ["⚠️ Configura tu API Key de Gemini en el archivo .env"]
        }

    # Ahora le pasamos hasta 80 comentarios al cerebro de Gemini para mayor precisión
    comments_text = "\n- ".join(raw_comments[:80]) if raw_comments else "No hay comentarios."

    prompt = f"""
    Eres un 'Media Buyer' y copywriter experto en marketing de afiliados para LATAM.
    Analizamos vender un producto '{product_type}' sobre: '{keyword}' en {country}.

    Comentarios de YouTube:
    {comments_text}

    Responde en JSON válido con esta estructura exacta:
    {{
        "social_saturation_score": [0 a 100. 100=Nicho virgen/Buena oportunidad, 10=Saturado],
        "social_label": "[Etiqueta corta. Ej: 'Interés validado en YouTube']",
        "meta_ads_score": [0 a 100. Estima la competencia publicitaria. 100=Pocos anunciantes/Océano azul, 10=Saturado],
        "meta_ads_label": "[Etiqueta corta. Ej: 'Estimado IA: Baja competencia']",
        "angles": [
            "💡 [Dolor/Deseo 1 extraído de los comentarios. Hook para anuncio]",
            "💡 [Dolor/Deseo 2...]",
            "💡 [Dolor/Deseo 3...]"
        ]
    }}

    Reglas:
    - Extrae solo 3 ángulos profundos (miedos, frustraciones, deseos).
    - IGNORA spam, links rotos o saludos.
    """

    try:
        response = ai_model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        import json
        return json.loads(response.text)
    except Exception as e:
        print(f"Error en IA: {e}")
        return {
            "social_saturation_score": 50, "social_label": "Error de IA",
            "meta_ads_score": 50, "meta_ads_label": "Error de IA",
            "angles": ["No se pudieron generar los ángulos."]
        }

# ─── 3. SCRAPER REAL DE META ADS (VÍA RAPIDAPI) ───────────────────────────────
def get_real_meta_ads_scraper(keyword, api_key):
    """
    Intenta extraer datos reales de Meta usando una API de scraping de terceros.
    Devuelve None si falla o no hay llave, para que la IA tome el control.
    """
    if not api_key:
        return None
        
    try:
        # Endpoint genérico. Reemplaza URL y Host según la API que contrates/uses en RapidAPI
        url = "https://facebook-ads-scraper.p.rapidapi.com/search"
        querystring = {"keyword": keyword, "limit": "50"}
        headers = {
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": "facebook-ads-scraper.p.rapidapi.com"
        }
        resp = requests.get(url, headers=headers, params=querystring, timeout=12)
        
        if resp.status_code == 200:
            ads = resp.json()
            ad_count = len(ads.get("data", []))
            
            if ad_count >= 15: score, label = 40, "Scraper: Muchos Ads Activos (Saturado)"
            elif ad_count >= 5: score, label = 70, "Scraper: Demanda Validada (Oportunidad)"
            else: score, label = 85, "Scraper: Pocos anunciantes"
            
            return {"score": score, "label": label, "source": "RapidAPI Scraper Real", "ad_count": ad_count}
        return None
    except Exception as e:
        print(f"Error Scraper Meta: {e}")
        return None

# ─── 4. MERCADO LIBRE ─────────────────────────────────────────────────────────
def get_mercadolibre_demand(keyword, country_code="BO"):
    ml_sites = {"BO": "MBO", "MX": "MLM", "AR": "MLA", "CO": "MCO", "CL": "MLC", "PE": "MPE"}
    site = ml_sites.get(country_code, "MBO")
    try:
        url = f"https://api.mercadolibre.com/sites/{site}/search?q={quote(keyword)}&limit=1"
        resp = requests.get(url, timeout=8)
        if resp.status_code == 200:
            total = resp.json().get("paging", {}).get("total", 0)
            if total > 5000: score, label = 30, "Mercado saturado"
            elif total > 500: score, label = 50, "Competencia alta"
            elif total > 50: score, label = 85, "Demanda validada"
            elif total > 5: score, label = 60, "Poca oferta"
            else: score, label = 40, "Nulo interés comercial"
            return {"score": score, "label": label, "source": f"Mercado Libre"}
        return {"score": 40, "label": "Error de conexión ML"}
    except Exception:
        return {"score": 40, "label": "Sin datos", "source": "Error"}

# ─── 5. GOOGLE AUTOCOMPLETE ───────────────────────────────────────────────────
def get_competition_score(keyword, country_code="BO"):
    try:
        gl = country_code.lower() if country_code != "LATAM" else "us"
        url = f"https://suggestqueries.google.com/complete/search?client=firefox&q={quote(keyword)}&hl=es&gl={gl}"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=6).json()
        suggestions = resp[1]
        commercial_terms = ["comprar", "precio", "opiniones", "curso", "descargar", "barato", "estafa", "pdf", "mercado libre"]
        commercial_count = sum(1 for s in suggestions if any(t in s.lower() for t in commercial_terms))
        
        if commercial_count >= 4: score, label = 30, "Competencia SEO extrema"
        elif commercial_count >= 2: score, label = 60, "Competencia moderada"
        else: score, label = 85, "Baja competencia en búsquedas"
        return {"score": score, "label": label, "source": "Google Autocomplete"}
    except Exception:
        return {"score": 55, "label": "Sin datos", "source": "Error"}

# ─── 6. ESTIMADOR DE MARGEN Y VIRALIDAD ───────────────────────────────────────
def estimate_margin(product_type, commission_input):
    if commission_input:
        match = re.search(r'(\d+)', commission_input)
        if match:
            pct = int(match.group(1))
            score = 70 if pct > 100 else min(95, int(pct * 1.3))
            return {"score": score, "label": f"Comisión del {pct}%", "source": "Dato usuario"}
    margins = {"digital": 70, "physical": 35, "service": 60, "hybrid": 50}
    return {"score": margins.get(product_type, 50), "label": "Estimado por industria", "source": "Interno"}

def estimate_viral_potential(product_type, platforms):
    base = 75 if product_type == "physical" else 60
    boost = sum({"TikTok": 20, "Instagram/Reels": 15, "YouTube": 10}.get(p, 0) for p in platforms[:3])
    final = min(95, base + boost)
    return {"score": final, "label": "Alto potencial" if final >= 70 else "Moderado", "source": "Plataformas"}

# ─── ENDPOINT PRINCIPAL ───────────────────────────────────────────────────────
@app.route("/api/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    keyword = data.get("product", "")
    product_type = data.get("productType", "digital")
    country = data.get("country", "BO")
    commission = data.get("commission", "")
    platforms = data.get("platforms", [])
    
    results = {}
    
    if product_type in ["physical", "hybrid"]:
        results["demand"] = get_mercadolibre_demand(keyword, country)
    else:
        results["demand"] = {"score": 80, "label": "Producto digital", "source": "N/A"}
        
    results["competition"] = get_competition_score(keyword, country)
    results["margin"] = estimate_margin(product_type, commission)
    results["viral_potential"] = estimate_viral_potential(product_type, platforms)
    
    # Análisis de YouTube con IA
    yt_data = get_raw_youtube_comments(keyword, YOUTUBE_API_KEY)
    ai_data = get_ai_insights(keyword, country, product_type, yt_data["comments"])
    
    results["social_interest"] = {
        "score": ai_data.get("social_saturation_score", 50),
        "label": ai_data.get("social_label", "Análisis IA"),
        "source": "Gemini AI"
    }
    
    # LÓGICA DE FALLBACK Y CONTEO DE ANUNCIOS: Scraper Real vs IA
    meta_ads_count = "Estimado por IA"
    real_meta_ads = get_real_meta_ads_scraper(keyword, RAPIDAPI_KEY)
    
    if real_meta_ads:
        # Extraemos el count que ahora envía la función para mandarlo al frontend
        meta_ads_count = real_meta_ads.get("ad_count", 0)
        results["meta_ads"] = real_meta_ads
    else:
        results["meta_ads"] = {
            "score": ai_data.get("meta_ads_score", 50),
            "label": ai_data.get("meta_ads_label", "Estimado por IA"),
            "source": "Gemini AI (Falta Scraper Key)"
        }
    
    weights = {"demand": 0.15, "meta_ads": 0.30, "social_interest": 0.20, "competition": 0.10, "margin": 0.15, "viral_potential": 0.10}
    overall = round(sum(results[k]["score"] * weights[k] for k in weights))
    verdict = "ALTA OPORTUNIDAD" if overall >= 70 else "VIABLE" if overall >= 45 else "EVITAR"
    
    return jsonify({
        "overall_score": overall,
        "verdict": verdict,
        "dimensions": results,
        "angles": ai_data.get("angles", []),
        "stats": {
            "videos": yt_data["videos_count"],
            "comments": yt_data["comments_count"],
            "meta_ads": meta_ads_count
        },
        "keyword": keyword,
        "country": country
    })

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True, port=5000)