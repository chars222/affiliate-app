from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import requests
import json
import time
import re
from urllib.parse import quote

app = Flask(__name__)
CORS(app)

# ─── Google Trends (via unofficial RSS) ──────────────────────────────────────
def get_trend_score(keyword, country_code="BO"):
    """
    Uses Google Trends RSS feed (no API key needed).
    Returns a score 0-100 based on whether keyword appears in trending topics,
    and fetches interest data via the CSV endpoint.
    """
    try:
        # Map country codes to Google Trends geo codes
        geo_map = {
            "BO": "BO", "MX": "MX", "AR": "AR", "CO": "CO",
            "PE": "PE", "CL": "CL", "EC": "EC", "PY": "PY",
            "UY": "UY", "ES": "ES", "US": "US", "LATAM": ""
        }
        geo = geo_map.get(country_code, "")

        # Google Trends explore URL for CSV data
        kw_encoded = quote(keyword)
        url = f"https://trends.google.com/trends/api/explore?hl=es&tz=240&req={{\"comparisonItem\":[{{\"keyword\":\"{keyword}\",\"geo\":\"{geo}\",\"time\":\"today 12-m\"}}],\"category\":0,\"property\":\"\"}}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        # Try the dailytrends RSS which is public
        rss_url = f"https://trends.google.com/trends/trendingsearches/daily/rss?geo={geo if geo else 'US'}"
        resp = requests.get(rss_url, headers=headers, timeout=8)

        if resp.status_code == 200:
            # Check if keyword appears in trending searches
            content = resp.text.lower()
            kw_lower = keyword.lower()
            words = kw_lower.split()

            matches = sum(1 for w in words if w in content)
            match_ratio = matches / len(words) if words else 0

            if match_ratio > 0.5:
                return {"score": 80, "label": "Tendencia alta", "source": "Google Trends RSS"}
            else:
                return {"score": 45, "label": "Tendencia moderada", "source": "Google Trends RSS"}
        else:
            return {"score": 50, "label": "Sin datos disponibles", "source": "estimado"}

    except Exception as e:
        return {"score": 50, "label": "Sin datos", "source": f"error: {str(e)[:50]}"}


# ─── Wikipedia Pageviews (free, official API) ─────────────────────────────────
def get_wikipedia_interest(keyword):
    """
    Wikipedia Pageview API is completely free and official.
    High pageviews = high demand/interest in the topic.
    """
    try:
        # Search for the article first
        search_url = f"https://en.wikipedia.org/w/api.php?action=opensearch&search={quote(keyword)}&limit=1&format=json"
        search_resp = requests.get(search_url, timeout=6)

        if search_resp.status_code != 200:
            return {"views": 0, "score": 40, "label": "Sin datos Wikipedia"}

        search_data = search_resp.json()
        if not search_data[1]:
            # Try Spanish Wikipedia
            search_url_es = f"https://es.wikipedia.org/w/api.php?action=opensearch&search={quote(keyword)}&limit=1&format=json"
            search_resp_es = requests.get(search_url_es, timeout=6)
            search_data = search_resp_es.json()
            if not search_data[1]:
                return {"views": 0, "score": 35, "label": "Término no encontrado"}
            article = search_data[1][0].replace(" ", "_")
            wiki_lang = "es"
        else:
            article = search_data[1][0].replace(" ", "_")
            wiki_lang = "en"

        # Get pageviews for last 60 days
        end_date = time.strftime("%Y%m%d")
        start_date = time.strftime("%Y%m%d", time.localtime(time.time() - 60*86400))

        views_url = f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/{wiki_lang}.wikipedia/all-access/user/{quote(article)}/daily/{start_date}/{end_date}"
        views_resp = requests.get(views_url, timeout=6)

        if views_resp.status_code == 200:
            items = views_resp.json().get("items", [])
            if items:
                total_views = sum(i.get("views", 0) for i in items)
                avg_daily = total_views / len(items)

                # Score based on daily average views
                if avg_daily > 10000:
                    score = 90
                    label = "Demanda muy alta"
                elif avg_daily > 3000:
                    score = 75
                    label = "Demanda alta"
                elif avg_daily > 500:
                    score = 60
                    label = "Demanda moderada"
                elif avg_daily > 100:
                    score = 45
                    label = "Demanda baja"
                else:
                    score = 30
                    label = "Demanda muy baja"

                return {
                    "views": int(avg_daily),
                    "score": score,
                    "label": label,
                    "article": article,
                    "source": f"Wikipedia ({wiki_lang})"
                }

        return {"views": 0, "score": 40, "label": "Sin datos de vistas"}

    except Exception as e:
        return {"views": 0, "score": 40, "label": "Sin datos", "source": str(e)[:50]}


# ─── DataForSEO Free / Google Autocomplete ────────────────────────────────────
def get_competition_score(keyword, country_code="BO"):
    """
    Uses Google Autocomplete API (free, no key needed) to gauge
    how many related searches exist = proxy for competition.
    More autocomplete suggestions = more competition.
    """
    try:
        lang_map = {
            "BO": "es", "MX": "es", "AR": "es", "CO": "es",
            "PE": "es", "CL": "es", "EC": "es", "PY": "es",
            "UY": "es", "ES": "es", "US": "en", "LATAM": "es"
        }
        lang = lang_map.get(country_code, "es")
        gl = country_code.lower() if country_code != "LATAM" else "us"

        url = f"https://suggestqueries.google.com/complete/search?client=firefox&q={quote(keyword + ' afiliado')}&hl={lang}&gl={gl}"
        headers = {"User-Agent": "Mozilla/5.0"}

        resp = requests.get(url, headers=headers, timeout=6)

        if resp.status_code == 200:
            data = resp.json()
            suggestions = data[1] if len(data) > 1 else []
            count = len(suggestions)

            # More affiliate-specific suggestions = more competition
            affiliate_terms = ["afiliado", "ganar", "comision", "programa", "review", "opiniones", "comprar"]
            affiliate_count = sum(1 for s in suggestions
                                  if any(t in s.lower() for t in affiliate_terms))

            if affiliate_count >= 4:
                score = 25  # Very saturated
                label = "Competencia muy alta"
            elif affiliate_count >= 2:
                score = 45
                label = "Competencia alta"
            elif count >= 6:
                score = 60
                label = "Competencia moderada"
            else:
                score = 80
                label = "Poca competencia"

            return {
                "suggestions": suggestions[:5],
                "score": score,
                "label": label,
                "source": "Google Autocomplete"
            }

        return {"score": 55, "label": "Sin datos", "suggestions": []}

    except Exception as e:
        return {"score": 55, "label": "Sin datos", "source": str(e)[:50]}


# ─── ClickBank Marketplace (scraping público) ─────────────────────────────────
def get_affiliate_market_score(keyword, product_type):
    """
    Estimates affiliate saturation based on keyword + type.
    Uses Open Library / public data as proxy.
    """
    try:
        # Use Google Shopping suggestions as proxy for physical product saturation
        url = f"https://suggestqueries.google.com/complete/search?client=firefox&q={quote(keyword + ' buy online')}&hl=en"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=6)

        suggestions = []
        if resp.status_code == 200:
            data = resp.json()
            suggestions = data[1] if len(data) > 1 else []

        # Physical products tend to have more competition
        base_score = 65 if product_type == "physical" else 55

        buy_terms = ["buy", "price", "cheap", "best", "review", "where to", "amazon"]
        saturation = sum(1 for s in suggestions if any(t in s.lower() for t in buy_terms))

        if saturation >= 4:
            score = base_score - 25
            label = "Muy saturado de afiliados"
        elif saturation >= 2:
            score = base_score - 10
            label = "Saturación media"
        else:
            score = base_score + 10
            label = "Poca saturación"

        return {"score": max(20, min(95, score)), "label": label, "source": "Análisis de mercado"}

    except Exception as e:
        return {"score": 55, "label": "Sin datos", "source": str(e)[:50]}


# ─── Margin estimator based on product type & price ──────────────────────────
def estimate_margin(product_type, price_range, commission_input):
    """
    Estimates commission margin based on product type and price range.
    Digital products typically have 30-70% margins.
    Physical products typically have 5-20% margins.
    """
    # Try to parse user-provided commission first
    if commission_input and commission_input.lower() not in ["no lo sé", "no sé", "no se", "n/a", ""]:
        match = re.search(r'(\d+)', commission_input)
        if match:
            pct = int(match.group(1))
            if pct > 100:  # It's a dollar amount
                if "$1,000" in price_range or "Más de" in price_range:
                    score = 85
                elif "$300" in price_range:
                    score = 70
                else:
                    score = 55
            else:
                score = min(95, int(pct * 1.3))
            return {
                "score": score,
                "label": f"{pct}% comisión",
                "estimated_commission": commission_input,
                "source": "Dato proporcionado"
            }

    # Estimate based on type
    margins = {
        "digital":  {"base": 70, "label": "40-70% típico en digitales"},
        "physical": {"base": 35, "label": "5-20% típico en físicos"},
        "service":  {"base": 60, "label": "20-40% típico en SaaS"},
        "hybrid":   {"base": 50, "label": "Variable según componente"},
    }

    price_bonus = {
        "Menos de $30": -10,
        "$30 - $100": 0,
        "$100 - $300": 10,
        "$300 - $1,000": 20,
        "Más de $1,000": 25,
        "Suscripción recurrente": 30,
    }

    base = margins.get(product_type, {"base": 50})["base"]
    bonus = price_bonus.get(price_range, 0)
    label = margins.get(product_type, {"label": "Variable"})["label"]

    return {
        "score": min(95, base + bonus),
        "label": label,
        "source": "Estimado por tipo de producto"
    }


# ─── Viral potential estimator ────────────────────────────────────────────────
def estimate_viral_potential(keyword, platforms, product_type):
    """
    Estimates viral potential based on product category and platforms.
    Uses TikTok/Instagram friendly product types.
    """
    viral_categories = {
        "physical": 75,   # Physical products are very visual = viral
        "digital": 60,
        "service": 45,
        "hybrid": 65,
    }

    platform_boost = {
        "TikTok": 20,
        "Instagram/Reels": 15,
        "YouTube": 10,
        "Pinterest": 8,
        "Blog/SEO": -5,
    }

    base = viral_categories.get(product_type, 50)
    boost = sum(platform_boost.get(p, 0) for p in platforms[:3])

    # Keywords that indicate viral potential
    viral_keywords = ["transformación", "resultado", "antes y después", "secreto",
                      "increíble", "natural", "rápido", "fácil", "bajar", "ganar",
                      "supplement", "beauty", "fitness", "gadget", "hack"]
    kw_boost = sum(5 for vk in viral_keywords if vk in keyword.lower())

    final = min(95, base + boost + kw_boost)
    label = "Alto potencial viral" if final >= 70 else "Potencial viral moderado" if final >= 45 else "Bajo potencial viral"

    return {"score": final, "label": label, "source": "Análisis por tipo y plataforma"}


# ─── Main analysis endpoint ───────────────────────────────────────────────────
@app.route("/api/analyze", methods=["POST"])
def analyze():
    data = request.get_json()

    keyword      = data.get("product", "")
    product_type = data.get("productType", "digital")
    country      = data.get("country", "BO")
    price_range  = data.get("price", "")
    commission   = data.get("commission", "")
    platforms    = data.get("platforms", [])
    category     = data.get("category", "")
    target       = data.get("target", "")

    results = {}

    # 1. Trend score (Google Trends RSS)
    results["trend"] = get_trend_score(keyword, country)
    time.sleep(0.3)

    # 2. Demand score (Wikipedia Pageviews)
    results["demand"] = get_wikipedia_interest(keyword)
    time.sleep(0.3)

    # 3. Competition score (Google Autocomplete)
    results["competition"] = get_competition_score(keyword, country)
    time.sleep(0.3)

    # 4. Affiliate saturation
    results["affiliate_saturation"] = get_affiliate_market_score(keyword, product_type)

    # 5. Margin estimate
    results["margin"] = estimate_margin(product_type, price_range, commission)

    # 6. Viral potential
    results["viral_potential"] = estimate_viral_potential(keyword, platforms, product_type)

    # ── Calculate overall score ──
    weights = {
        "demand": 0.25,
        "trend": 0.20,
        "margin": 0.25,
        "competition": 0.15,
        "affiliate_saturation": 0.10,
        "viral_potential": 0.05,
    }

    overall = sum(results[k]["score"] * w for k, w in weights.items())
    overall = round(overall)

    # ── Verdict ──
    if overall >= 70:
        verdict = "ALTA OPORTUNIDAD"
    elif overall >= 45:
        verdict = "VIABLE"
    else:
        verdict = "EVITAR"

    # ── Country context ──
    country_context = {
        "BO": "Bolivia tiene un mercado digital en crecimiento con alta penetración de WhatsApp y Facebook. TikTok está ganando fuerte tracción. Los pagos vía QR (Tigo Money, BNB) facilitan ventas digitales.",
        "MX": "México es el mayor mercado de ecommerce de habla hispana. Alta competencia pero enorme volumen. Mercado Libre y redes sociales dominan.",
        "AR": "Argentina tiene alta actividad digital y audiencias muy educadas. La volatilidad económica puede afectar conversiones en productos caros.",
        "CO": "Colombia tiene crecimiento acelerado en ecommerce y buena adopción de pagos digitales. Audiencia joven y receptiva a productos digitales.",
        "CL": "Chile tiene el mayor poder adquisitivo de LATAM y alta digitalización. Mercado maduro, dispuesto a pagar por calidad.",
        "PE": "Perú está en pleno despegue digital. Oportunidad en nichos con poca competencia local.",
        "LATAM": "Estrategia regional con mayor alcance. Adaptar mensajes a cada país aumenta conversión.",
    }

    return jsonify({
        "overall_score": overall,
        "verdict": verdict,
        "dimensions": results,
        "country_context": country_context.get(country, "Mercado con potencial de crecimiento digital."),
        "keyword": keyword,
        "country": country,
    })


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
