"""
Backend Flask del Sistema NLP de Reportes Ciudadanos (PE-311).

Sirve el front (static/index.html) y expone la API que lo conecta con los
modelos BETO y con la persistencia en CSV.

Arranque:  python server.py     (o usar ../run.ps1 / ../run.sh)
"""
import re

from flask import Flask, jsonify, request, send_from_directory

import config as C
import ml
import store

app = Flask(__name__, static_folder="static", static_url_path="")

EMAIL_RE = re.compile(r"\S+@\S+\.\S+")
CEL_RE = re.compile(r"^9\d{8}$")


# ---------------------------------------------------------------------------
# Front
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


# ---------------------------------------------------------------------------
# Metadatos (opciones de formularios y filtros)
# ---------------------------------------------------------------------------
@app.route("/api/meta")
def meta():
    return jsonify({
        "locations": store.location_tree(),
        "sectores": [{"value": k, "label": v} for k, v in C.SECTOR_LABELS.items()],
        "areas": list(C.AREA_LABELS.values()),
        "gravedades": ["Alta", "Media", "Baja"],
        "estados": list(C.ESTADO_LABELS.values()),
        "contacts": C.MUNICIPAL_CONTACTS,
        "sevColor": C.SEV_COLOR,
        "estColor": C.EST_COLOR,
        "deptMapPos": C.DEPT_MAP_POS,
        "backend": ml.BACKEND,
        "adminDni": C.ADMIN_DNI,
    })


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
@app.route("/api/login", methods=["POST"])
def login():
    body = request.get_json(force=True) or {}
    role = body.get("role", "ciudadano")
    dni = re.sub(r"\D", "", str(body.get("dni", "")))

    if not dni:
        return jsonify({"error": "Ingresa un DNI numérico."}), 400

    if role == "admin":
        return jsonify({"dni": dni, "nombre": C.ADMIN_NOMBRE, "type": "admin"})

    # ciudadano: si el DNI existe en persistencia usamos su nombre; si no, cuenta nueva
    nombre = store.name_for_dni(dni)
    if not nombre:
        nombre = f"Ciudadano {dni}"
    return jsonify({"dni": dni, "nombre": nombre, "type": "ciudadano"})


# ---------------------------------------------------------------------------
# Tickets
# ---------------------------------------------------------------------------
@app.route("/api/tickets")
def tickets():
    owner = request.args.get("owner_dni")
    data = store.tickets_by_dni(owner) if owner else store.all_tickets()
    return jsonify(data)


@app.route("/api/tickets/<path:codigo>/estado", methods=["PATCH"])
def cambiar_estado(codigo):
    body = request.get_json(force=True) or {}
    estado = body.get("estado", "")
    if store.update_estado(codigo, estado):
        return jsonify({"ok": True})
    return jsonify({"error": "Ticket o estado inválido."}), 400


# ---------------------------------------------------------------------------
# Crear reporte (dispara la clasificación NLP)
# ---------------------------------------------------------------------------
@app.route("/api/reports", methods=["POST"])
def crear_reporte():
    b = request.get_json(force=True) or {}

    descripcion = (b.get("descripcion") or "").strip()
    nombres = (b.get("nombres") or "").strip()
    correo = (b.get("correo") or "").strip()
    celular = (b.get("celular") or "").strip()
    sector_code = (b.get("sector") or "").strip()
    departamento = (b.get("departamento") or "").strip()
    provincia = (b.get("provincia") or "").strip()
    distrito = (b.get("distrito") or "").strip()
    dni = re.sub(r"\D", "", str(b.get("dni", ""))) or "0"
    file_names = b.get("fileNames") or []

    # Validación de servidor (espejo de la del front)
    faltan = []
    if not departamento or not provincia or not distrito:
        faltan.append("ubicación")
    if not nombres:
        faltan.append("nombres")
    if not EMAIL_RE.search(correo):
        faltan.append("correo")
    if not CEL_RE.match(celular):
        faltan.append("celular")
    if sector_code not in C.SECTOR_LABELS:
        faltan.append("sector")
    if len(descripcion) < 10:
        faltan.append("descripción")
    if faltan:
        return jsonify({"error": "Datos incompletos o inválidos: " + ", ".join(faltan)}), 400

    # Clasificación NLP (BETO real o fallback)
    result = ml.classify(descripcion)

    evidencia_label = f"[ {', '.join(file_names)} ]" if file_names else "Sin evidencia adjunta"
    ticket = store.add_report(
        descripcion=descripcion, nombre=nombres, correo=correo, celular=celular,
        sector_code=sector_code, departamento=departamento, provincia=provincia,
        distrito=distrito, dni=dni,
        complaint_type=result["complaint_type"], priority=result["priority"],
        confianza=result["confidence"], evidencia_label=evidencia_label,
        attachment_count=len(file_names),
    )
    return jsonify({
        "ticket": ticket,
        "analysis": {
            "area": result["area"],
            "gravedad": result["gravedad"],
            "confidence": result["confidence"],
            "keywords": result["keywords"],
            "backend": result["backend"],
        },
    })


# ---------------------------------------------------------------------------
def main():
    print("=" * 62)
    print(" Sistema NLP Reportes Ciudadanos — arrancando")
    print("=" * 62)
    store.load()
    ml.load()
    print("-" * 62)
    print(" Front disponible en:  http://127.0.0.1:5000")
    print(f" Backend NLP:          {ml.BACKEND}")
    print("=" * 62)
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)


if __name__ == "__main__":
    main()
