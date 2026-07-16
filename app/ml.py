"""
Motor de clasificación NLP.

Carga los dos modelos BETO ya entrenados (tipo de incidente y prioridad) desde
la carpeta `pesos/` y expone `classify(texto)`. Si torch/transformers o los pesos
no están disponibles, cae de forma transparente a un clasificador por palabras
clave, de modo que la app siempre queda funcional.

El preprocesamiento (`limpiar_texto`) replica exactamente el del notebook.
"""
import os
import re
import unicodedata

import config as C

# --- Lexicón de palabras clave por área (para los "chips" del front y el fallback) ---
AREA_KEYWORDS = {
    "AGUA_Y_SANEAMIENTO":    ["agua", "fuga", "tuberia", "tubería", "desague", "desagüe",
                               "alcantarilla", "potable", "buzon", "buzón", "saneamiento", "atorado"],
    "ALUMBRADO_PUBLICO":     ["luminaria", "poste", "alumbrado", "foco", "luz", "apagado",
                               "oscuras", "intermitente", "farola"],
    "AREAS_VERDES":          ["arbol", "árbol", "parque", "poda", "jardin", "jardín", "ramas",
                               "maleza", "grass", "area verde", "área verde"],
    "CONTAMINACION_Y_RUIDO": ["ruido", "humo", "contaminacion", "contaminación", "olores",
                               "quema", "bulla", "humareda"],
    "LIMPIEZA_PUBLICA":      ["basura", "residuos", "desmonte", "recojo", "limpieza",
                               "acumulacion", "acumulación", "desechos"],
    "SEGURIDAD_CIUDADANA":   ["robo", "asalto", "camara", "cámara", "serenazgo", "delincuencia",
                               "inseguridad", "sospechos", "arma"],
    "TRANSPORTE_Y_TRANSITO": ["semaforo", "semáforo", "transito", "tránsito", "paradero",
                               "vehiculo", "vehículo", "señalizacion", "congestion", "congestión"],
    "VIA_PUBLICA":           ["bache", "pista", "vereda", "pavimento", "hueco", "calzada",
                               "cuneta", "sardinel"],
}

# Palabras que sugieren gravedad (solo para el fallback)
SEV_KEYWORDS = [
    ("ALTA", ["arma", "armada", "incendio", "derrumbe", "grieta", "herido", "peligro",
              "riesgo", "colaps", "cable caido", "cable caído", "fuga"]),
    ("MEDIA", ["accidente", "choque", "prolongado", "inundacion", "inundación", "asalto",
               "congestion", "congestión", "atorado", "roto"]),
    ("BAJA", ["ruido", "basura", "olores", "informal", "maleza", "pintura"]),
]

BACKEND = "no-cargado"   # 'beto' | 'fallback'
_type_model = _type_tok = None
_priority_model = _priority_tok = None
_torch = None


# ---------------------------------------------------------------------------
def limpiar_texto(t: str) -> str:
    """Normalización mínima y no destructiva (idéntica a la del entrenamiento)."""
    if not isinstance(t, str):
        return ""
    t = unicodedata.normalize("NFC", t)
    t = t.replace(" ", " ")
    t = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def load():
    """Intenta cargar los modelos BETO. Define BACKEND según el resultado."""
    global BACKEND, _type_model, _type_tok, _priority_model, _priority_tok, _torch
    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        _torch = torch

        for path in (C.MODEL_TYPE_DIR, C.MODEL_PRIORITY_DIR):
            if not os.path.isdir(path):
                raise FileNotFoundError(f"No se encuentran los pesos en {path}")

        print("[ml] Cargando modelo de tipo (complaint_type)…")
        _type_tok = AutoTokenizer.from_pretrained(C.MODEL_TYPE_DIR)
        _type_model = AutoModelForSequenceClassification.from_pretrained(C.MODEL_TYPE_DIR).eval()

        print("[ml] Cargando modelo de prioridad…")
        _priority_tok = AutoTokenizer.from_pretrained(C.MODEL_PRIORITY_DIR)
        _priority_model = AutoModelForSequenceClassification.from_pretrained(C.MODEL_PRIORITY_DIR).eval()

        BACKEND = "beto"
        print("[ml] Modelos BETO cargados. Backend = beto")
    except Exception as e:  # noqa: BLE001
        BACKEND = "fallback"
        print(f"[ml] No se pudieron cargar los modelos BETO ({type(e).__name__}: {e}).")
        print("[ml] Se usará el clasificador por palabras clave. Backend = fallback")


# ---------------------------------------------------------------------------
def _beto_predict(text, model, tok):
    """Devuelve (etiqueta, probabilidad_top) para un modelo BETO."""
    enc = tok([text], truncation=True, max_length=C.MAX_LENGTH, return_tensors="pt")
    with _torch.no_grad():
        logits = model(**enc).logits
        probs = _torch.softmax(logits, dim=-1)[0]
    idx = int(_torch.argmax(probs).item())
    label = model.config.id2label[idx]
    return label, float(probs[idx].item())


def _keywords_for(text_lower, complaint_type):
    hits = [kw for kw in AREA_KEYWORDS.get(complaint_type, []) if kw in text_lower]
    # normaliza duplicados por acentos y recorta
    seen, out = set(), []
    for kw in hits:
        base = unicodedata.normalize("NFKD", kw).encode("ascii", "ignore").decode()
        if base not in seen:
            seen.add(base)
            out.append(kw)
    return out[:5]


def _fallback_classify(clean, lower):
    best_ct, best_score = None, 0
    for ct, kws in AREA_KEYWORDS.items():
        score = sum(1 for kw in kws if kw in lower)
        if score > best_score:
            best_score, best_ct = score, ct
    if not best_ct:
        best_ct = "VIA_PUBLICA"
    priority = "MEDIA"
    for pr, kws in SEV_KEYWORDS:
        if any(kw in lower for kw in kws):
            priority = pr
            break
    confidence = min(96, 70 + best_score * 7 + len(lower) % 5)
    return best_ct, priority, confidence


def classify(text: str) -> dict:
    """
    Clasifica un reporte. Devuelve:
      complaint_type, priority  -> etiquetas crudas (para persistir)
      area, gravedad            -> etiquetas legibles (para el front)
      confidence                -> % de confianza del modelo de tipo
      keywords                  -> lista de términos detectados
      backend                   -> 'beto' o 'fallback'
    """
    clean = limpiar_texto(text)
    lower = clean.lower()

    if BACKEND == "beto":
        complaint_type, ct_conf = _beto_predict(clean, _type_model, _type_tok)
        priority, _pr_conf = _beto_predict(clean, _priority_model, _priority_tok)
        confidence = round(ct_conf * 100)
    else:
        complaint_type, priority, confidence = _fallback_classify(clean, lower)

    keywords = _keywords_for(lower, complaint_type)
    if not keywords:
        keywords = ["sin coincidencias claras"]

    return {
        "complaint_type": complaint_type,
        "priority": priority,
        "area": C.AREA_LABELS.get(complaint_type, complaint_type),
        "gravedad": C.GRAVEDAD_LABELS.get(priority.upper(), "NA"),
        "confidence": int(confidence),
        "keywords": keywords,
        "backend": BACKEND,
    }
