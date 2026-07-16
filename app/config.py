"""
Configuración central de la app (rutas y mapeos del "cruce de datos").

Aquí viven las tablas que traducen los códigos del dataset / modelos BETO
a las etiquetas legibles que muestra el front. Si cambia el dataset o se
reentrena el modelo con otras clases, este es el único archivo a tocar.
"""
import os

# --- Rutas base ---------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))          # .../app
ROOT_DIR = os.path.dirname(BASE_DIR)                            # .../nlp-hackaton

# CSV fuente (dataset original entregado, se deja intacto)
SOURCE_CSV = os.path.join(ROOT_DIR, "pe311_reportes_sinteticos.csv")

# Copias que genera la app en el primer arranque
DATA_DIR = os.path.join(BASE_DIR, "data")
TRAIN_CSV = os.path.join(DATA_DIR, "pe311_entrenamiento.csv")   # copia para entrenar
PERSIST_CSV = os.path.join(DATA_DIR, "pe311_persistencia.csv")  # copia + dni (persistencia)

CSV_DELIM = ";"

# Pesos de los modelos BETO ya entrenados
PESOS_DIR = os.path.join(ROOT_DIR, "pesos")
MODEL_TYPE_DIR = os.path.join(PESOS_DIR, "modelo_beto_pe311_type", "beto_pe311", "modelo_final")
MODEL_PRIORITY_DIR = os.path.join(PESOS_DIR, "modelo_beto_pe311_priority", "beto_pe311", "modelo_final")
MAX_LENGTH = 128  # mismo valor usado en el entrenamiento (ver notebook)

# DNI sintético: se asigna uno por nombre único, empezando en este valor.
DNI_INICIAL = 4000

# --- Mapeos código dataset  ->  etiqueta legible ------------------------------

# complaint_type (8 clases del modelo "type") -> Área derivada
AREA_LABELS = {
    "AGUA_Y_SANEAMIENTO":     "Agua y Saneamiento",
    "ALUMBRADO_PUBLICO":      "Alumbrado Público",
    "AREAS_VERDES":           "Áreas Verdes",
    "CONTAMINACION_Y_RUIDO":  "Contaminación y Ruido",
    "LIMPIEZA_PUBLICA":       "Limpieza Pública",
    "SEGURIDAD_CIUDADANA":    "Seguridad Ciudadana",
    "TRANSPORTE_Y_TRANSITO":  "Transporte y Tránsito",
    "VIA_PUBLICA":            "Vía Pública",
}

# priority (3 clases del modelo "priority") -> Gravedad
GRAVEDAD_LABELS = {"ALTA": "Alta", "MEDIA": "Media", "BAJA": "Baja"}

# status (6 estados del dataset) -> etiqueta legible
ESTADO_LABELS = {
    "RECIBIDO":   "Recibido",
    "ASIGNADO":   "Asignado",
    "EN_PROCESO": "En proceso",
    "DERIVADO":   "Derivado",
    "CERRADO":    "Cerrado",
    "RECHAZADO":  "Rechazado",
}
# Estado inicial de un reporte nuevo creado desde el formulario
ESTADO_INICIAL = "RECIBIDO"

# sector (3 valores del dataset) -> etiqueta legible
SECTOR_LABELS = {
    "CIUDADANO":           "Ciudadano",
    "INSTITUCION_PRIVADA": "Privado",
    "INSTITUCION_PUBLICA": "Público",
}

# --- Colores (se replican del diseño original) --------------------------------
SEV_COLOR = {
    "Alta":  {"bg": "oklch(93% 0.08 35)",  "fg": "oklch(45% 0.18 35)",  "dot": "oklch(60% 0.2 35)"},
    "Media": {"bg": "oklch(94% 0.07 85)",  "fg": "oklch(45% 0.12 85)",  "dot": "oklch(78% 0.15 85)"},
    "Baja":  {"bg": "oklch(93% 0.05 165)", "fg": "oklch(38% 0.1 165)",  "dot": "oklch(65% 0.13 165)"},
    "NA":    {"bg": "oklch(94% 0.005 260)","fg": "oklch(45% 0.01 260)", "dot": "oklch(65% 0.01 260)"},
}
EST_COLOR = {
    "Recibido":   {"bg": "oklch(94% 0.05 220)", "fg": "oklch(40% 0.12 220)"},
    "Asignado":   {"bg": "oklch(93% 0.05 260)", "fg": "oklch(42% 0.12 260)"},
    "En proceso": {"bg": "oklch(94% 0.07 85)",  "fg": "oklch(45% 0.12 85)"},
    "Derivado":   {"bg": "oklch(93% 0.06 300)", "fg": "oklch(45% 0.13 300)"},
    "Cerrado":    {"bg": "oklch(93% 0.06 145)", "fg": "oklch(40% 0.13 145)"},
    "Rechazado":  {"bg": "oklch(93% 0.05 25)",  "fg": "oklch(45% 0.16 25)"},
}

# Posición referencial (x,y en %) de cada departamento para el mapa del dashboard
DEPT_MAP_POS = {
    "LIMA":        {"x": 30, "y": 58},
    "CALLAO":      {"x": 26, "y": 57},
    "AREQUIPA":    {"x": 40, "y": 84},
    "CUSCO":       {"x": 54, "y": 74},
    "PIURA":       {"x": 16, "y": 14},
    "LA LIBERTAD": {"x": 22, "y": 34},
    "LAMBAYEQUE":  {"x": 18, "y": 24},
}


def _slug_correo(area_label: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", area_label).encode("ascii", "ignore").decode()
    return s.lower().replace(" y ", "").replace(" ", "")


# Contacto municipal por área (correo/teléfono de seguimiento) generado a partir del nombre
MUNICIPAL_CONTACTS = {
    label: {
        "correo": f"{_slug_correo(label)}@municipalidaddigital.gob.pe",
        "telefono": f"(01) 555-0102 anexo {200 + i}",
    }
    for i, label in enumerate(AREA_LABELS.values(), start=1)
}

# Cuenta de administrador de demostración
ADMIN_DNI = "99999999"
ADMIN_NOMBRE = "Administrador Municipal"
