"""
Reference content for the EWS Guide help chat.

Mirrors frontend/src/components/HelpChat.jsx's QA content — this is the
knowledge base the Gemini-backed help endpoint is constrained to (RAG-style:
retrieve the closest matching entries, feed only those to the model, never
let it answer from general knowledge). Keep the two in sync when either
changes.
"""

from __future__ import annotations

QA: list[dict] = [
    {
        "triggers": ["what is a landslide", "landslide", "define landslide"],
        "answer": (
            "A landslide is when a mass of soil, rock, or debris suddenly breaks loose from a hillside "
            "and flows downhill — often in seconds, with no warning. Northern Province Rwanda is one of "
            "the highest-risk areas in East Africa: steep volcanic hillside, deep clay soil that absorbs "
            "water heavily, and intense multi-day rainy-season rainfall. Between 2007 and 2020, Northern "
            "Province recorded over 200 landslide fatalities. This system exists to give officers advance warning."
        ),
    },
    {
        "triggers": ["why is this important", "why does it matter", "why build this", "impact"],
        "answer": (
            "The danger isn't a single heavy rainstorm — it's accumulated rainfall over several days "
            "saturating the soil until one more trigger causes the slope to fail. By the time a landslide "
            "is visible, it's already moving; there is no safe reaction time. An early warning gives field "
            "officers hours, not seconds, to act. That's why the alert threshold is intentionally low (5%) "
            "— better to send more warnings than miss a real event."
        ),
    },
    {
        "triggers": ["how does it work", "how does the system work", "overview", "getting started", "end to end"],
        "answer": (
            "Every morning: (1) NASA satellites measure yesterday's rainfall across Northern Province "
            "(GPM IMERG, falls back to CHIRPS). (2) The system already knows each of 250 slope units' "
            "terrain, soil, and vegetation. (3) An XGBoost model combines today's rainfall with that "
            "terrain data and scores every unit 0-100% risk — the most important factor is rainfall over "
            "the past 5 days, not just today. (4) Any unit scoring 5%+ triggers an SMS to the district "
            "officer (3% if a nearby earthquake was detected in the last 48h). (5) The officer checks the "
            "location and replies YES or NO to confirm or dispute — that feedback is tracked as real-world accuracy."
        ),
    },
    {
        "triggers": ["risk map", "map", "colour", "color", "polygon"],
        "answer": (
            "The Risk Map shows all 250 slope units as coloured polygons: green (below 50%), amber "
            "(50-79%), red (80%+, SMS sent). Click a polygon for unit ID, district, sector, and risk %. "
            "The map always shows the most recent pipeline run — run the pipeline to refresh it."
        ),
    },
    {
        "triggers": ["pipeline", "run pipeline", "trigger", "cron", "schedule", "daily"],
        "answer": (
            "The pipeline runs every morning (01:00 AM Kigali time via GitHub Actions, or manually via "
            "Run Pipeline). It downloads yesterday's rainfall, checks for nearby earthquakes, builds the "
            "feature matrix, scores all 250 units, saves predictions, and sends SMS alerts to any unit "
            "above threshold."
        ),
    },
    {
        "triggers": ["alert", "sms", "dispatch", "who gets the sms"],
        "answer": (
            "SMS alerts fire automatically when a slope unit exceeds the risk threshold. Each message "
            "includes district, sector, risk level, GPS coordinates, the main driver, and reply "
            "instructions (YES/NO to confirm or dispute). Alerts go through Africa's Talking and Telerivet "
            "in parallel for delivery reliability on MTN Rwanda."
        ),
    },
    {
        "triggers": ["seismic", "earthquake", "usgs", "tremor"],
        "answer": (
            "The system checks the USGS Earthquake API on every pipeline run. A magnitude 4.0+ earthquake "
            "within 200km in the last 48 hours automatically lowers the alert threshold from 5% to 3% — "
            "earthquakes loosen soil and make slopes more vulnerable to rainfall-triggered failure."
        ),
    },
    {
        "triggers": ["slope unit", "what is a slope unit", "396"],
        "answer": (
            "A slope unit is a section of hillside bounded by ridge and valley lines that drains water in "
            "one consistent direction — a more meaningful grouping for landslide risk than a flat pixel "
            "grid. The system tracks 250 of them across Northern Province."
        ),
    },
    {
        "triggers": ["predict", "prediction", "predict panel", "by slope unit"],
        "answer": (
            "The Predict tab has two modes. 'By Slope Unit' (the default) lets you pick a real district "
            "and slope unit and see its current live assessment — no data entry needed. 'Advanced / "
            "Scenario Testing' lets you type in hypothetical feature values to explore what-if scenarios; "
            "it's for testing, not real conditions."
        ),
    },
    {
        "triggers": ["district", "districts", "gakenke", "burera", "musanze", "gicumbi", "rulindo"],
        "answer": (
            "The Districts tab summarises each of the 5 monitored districts: peak risk today, slope units "
            "monitored, alerts in the last 7 days, and the highest-risk sector. Updates after every pipeline run."
        ),
    },
    {
        "triggers": ["data source", "rainfall data", "satellite", "imerg", "chirps"],
        "answer": (
            "Rainfall: GPM IMERG (primary, ~14h lag) with CHIRPS as fallback. Terrain: elevation-derived "
            "slope/aspect/wetness index. Vegetation: Sentinel-2 NDVI. Soil: ISRIC SoilGrids. Seismic: USGS "
            "Earthquake Hazards API. SMS: Africa's Talking + Telerivet."
        ),
    },
    {
        "triggers": ["model", "xgboost", "machine learning", "accuracy", "how accurate"],
        "answer": (
            "The model is XGBoost, trained on historical rainfall and terrain data for Northern Province. "
            "Cross-validated AUC: 0.959, false negative rate 8.3% at the production threshold. The single "
            "most important feature is 5-day antecedent rainfall (46% importance), followed by 3-day "
            "antecedent rainfall (33%)."
        ),
    },
    {
        "triggers": ["antecedent", "3-day", "5-day", "prior rainfall", "soil saturation"],
        "answer": (
            "Antecedent rainfall is how much rain fell in the days before today — it tells the model how "
            "saturated the soil already is. 5-day total is the single most important model feature; above "
            "150mm is critical. A 30mm storm on soil that already received 120mm in the past week is far "
            "more dangerous than 30mm on dry ground."
        ),
    },
    {
        "triggers": ["twi", "topographic wetness", "ndvi", "vegetation index"],
        "answer": (
            "TWI (Topographic Wetness Index) measures where water naturally collects; above 12 is "
            "critical. NDVI measures vegetation density from satellite imagery (-1 to 1); below 0.35 "
            "means sparse vegetation and less root cohesion holding soil together."
        ),
    },
    {
        "triggers": ["threshold", "5%", "alert threshold", "why 5"],
        "answer": (
            "The SMS alert threshold is 5% probability — intentionally low, because in a life-safety "
            "system it's better to send more precautionary alerts than miss a real event. It drops to 3% "
            "after a nearby earthquake."
        ),
    },
    {
        "triggers": ["feedback", "confirm", "denied", "officer feedback", "yes no reply"],
        "answer": (
            "After an SMS alert, officers reply YES [unit_id] to confirm ground conditions match, or NO "
            "[unit_id] to report a false alarm. This feedback is logged in the Alerts tab and tracks the "
            "system's real-world confirmation rate over time."
        ),
    },
    {
        "triggers": ["why northern province", "why 5 districts", "coverage", "scope"],
        "answer": (
            "The system covers Gakenke, Burera, Musanze, Gicumbi, and Rulindo — all five districts of "
            "Northern Province — because the region has Rwanda's highest historical landslide rate, the "
            "model was trained and calibrated specifically for this region's soils and slopes, and MINEMA "
            "has designated it the primary early-warning zone."
        ),
    },
    {
        "triggers": ["what does this not do", "limitations", "not replace"],
        "answer": (
            "This system does not replace MINEMA or Meteo Rwanda — alerts are decision support, not "
            "evacuation orders. It does not pinpoint an exact landslide location, only elevated-risk slope "
            "units. It has no ground rain gauges (satellite estimates only, ~14h delay). It covers only "
            "Northern Province, and was trained on a small number of confirmed events."
        ),
    },
]

FALLBACK = (
    "I'm not sure about that. Try asking: How does the system work? What does the pipeline do? "
    "What is a slope unit? When are SMS alerts sent? What data sources does it use? "
    "How accurate is the model? What does the system not do?"
)


def top_matches(question: str, k: int = 3) -> list[dict]:
    """Word-overlap retrieval — same scoring approach as the frontend fallback bot."""
    lower = question.lower()
    words = set(w for w in __import__("re").split(r"\W+", lower) if len(w) > 2)

    scored = []
    for entry in QA:
        trigger_words = set(
            w for t in entry["triggers"] for w in t.split() if len(w) > 2
        )
        score = len(words & trigger_words)
        if any(t in lower for t in entry["triggers"]):
            score += 5
        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [entry for _, entry in scored[:k]]


def rule_based_answer(question: str) -> str:
    matches = top_matches(question, k=1)
    return matches[0]["answer"] if matches else FALLBACK
