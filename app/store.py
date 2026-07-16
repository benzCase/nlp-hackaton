"""
Capa de persistencia sobre CSV (sin dependencias externas, solo stdlib).

En el primer arranque genera dos copias del dataset original:
  * pe311_entrenamiento.csv  -> copia intacta para reentrenar el modelo
  * pe311_persistencia.csv   -> copia + columna `dni` (y `confianza`, `evidencia`)
                                sobre la que la app lee y escribe reportes nuevos.

El DNI se asigna uno por nombre único empezando en DNI_INICIAL (4000). Si un
nombre se repite, comparte DNI (riesgo asumido); los reportes creados desde el
formulario se guardan con el DNI del ciudadano en sesión.
"""
import csv
import os
import shutil
import threading
from datetime import datetime

import config as C

_LOCK = threading.RLock()
_TICKETS = []          # lista de dicts "ticket" listos para el front (orden: más nuevo primero)
_DNI_BY_NAME = {}      # nombre -> dni (str)
_FIELDNAMES = []       # columnas del CSV de persistencia
_EXTRA_COLS = ["dni", "confianza", "evidencia"]


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def _parse_fecha(s):
    """Parsea 'D/M/YYYY H:M' (formato del dataset). Devuelve datetime o None."""
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _fmt_fecha(dt):
    return f"{dt.day:02d}/{dt.month:02d}/{dt.year}" if dt else ""


def _evidencia_desde_adjuntos(n):
    try:
        n = int(float(n))
    except (TypeError, ValueError):
        n = 0
    return f"{n} archivo(s) adjunto(s)" if n > 0 else "Sin evidencia adjunta"


# ---------------------------------------------------------------------------
# Construcción del CSV de persistencia
# ---------------------------------------------------------------------------
def _build_persistencia():
    """Crea data/ con las dos copias del CSV si aún no existen."""
    os.makedirs(C.DATA_DIR, exist_ok=True)

    if not os.path.exists(C.SOURCE_CSV):
        raise FileNotFoundError(f"No se encuentra el dataset origen: {C.SOURCE_CSV}")

    # Copia de entrenamiento (intacta)
    if not os.path.exists(C.TRAIN_CSV):
        shutil.copyfile(C.SOURCE_CSV, C.TRAIN_CSV)

    # Copia de persistencia con dni asignado por nombre
    if not os.path.exists(C.PERSIST_CSV):
        with open(C.SOURCE_CSV, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter=C.CSV_DELIM)
            base_cols = reader.fieldnames
            rows = list(reader)

        name_to_dni = {}
        next_dni = C.DNI_INICIAL
        for r in rows:
            nombre = (r.get("reporter_name") or "").strip()
            if nombre not in name_to_dni:
                name_to_dni[nombre] = str(next_dni)
                next_dni += 1
            r["dni"] = name_to_dni[nombre]
            r["confianza"] = ""  # el modelo no reevalúa filas históricas
            r["evidencia"] = _evidencia_desde_adjuntos(r.get("attachment_count"))

        out_cols = list(base_cols) + _EXTRA_COLS
        with open(C.PERSIST_CSV, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=out_cols, delimiter=C.CSV_DELIM)
            writer.writeheader()
            writer.writerows(rows)
        print(f"[store] Persistencia creada: {C.PERSIST_CSV} "
              f"({len(rows)} filas, {len(name_to_dni)} DNIs desde {C.DNI_INICIAL})")


# ---------------------------------------------------------------------------
# Carga en memoria
# ---------------------------------------------------------------------------
def _row_to_ticket(r):
    dt = _parse_fecha(r.get("created_date"))
    area = C.AREA_LABELS.get((r.get("complaint_type") or "").strip(),
                             (r.get("complaint_type") or "").strip() or "—")
    gravedad = C.GRAVEDAD_LABELS.get((r.get("priority") or "").strip().upper(), "NA")
    estado = C.ESTADO_LABELS.get((r.get("status") or "").strip().upper(), "Recibido")
    sector = C.SECTOR_LABELS.get((r.get("sector") or "").strip(), (r.get("sector") or "").strip())
    dep = (r.get("departamento") or "").strip()
    prov = (r.get("provincia") or "").strip()
    dist = (r.get("distrito") or "").strip()
    conf = (r.get("confianza") or "").strip()
    return {
        "codigo": (r.get("unique_key") or "").strip(),
        "fechaIso": dt.strftime("%Y-%m-%d") if dt else "",
        "fechaFmt": _fmt_fecha(dt),
        "departamento": dep, "provincia": prov, "distrito": dist,
        "ubicacion": ", ".join([x for x in (dist, prov, dep) if x]),
        "nombre": (r.get("reporter_name") or "").strip(),
        "correo": (r.get("reporter_email") or "").strip(),
        "celular": (r.get("reporter_phone") or "").strip(),
        "sector": sector,
        "descripcion": (r.get("descriptor_raw") or "").strip(),
        "area": area,
        "gravedad": gravedad,
        "estado": estado,
        "confianza": int(float(conf)) if conf else None,
        "evidenciaLabel": (r.get("evidencia") or "").strip() or "Sin evidencia adjunta",
        "ownerDni": (r.get("dni") or "").strip(),
    }


def load():
    """Carga (o recarga) el CSV de persistencia a memoria."""
    global _TICKETS, _DNI_BY_NAME, _FIELDNAMES
    with _LOCK:
        _build_persistencia()
        with open(C.PERSIST_CSV, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter=C.CSV_DELIM)
            _FIELDNAMES = reader.fieldnames
            rows = list(reader)
        _TICKETS = [_row_to_ticket(r) for r in rows]
        # más reciente primero (los sin fecha al final)
        _TICKETS.sort(key=lambda t: t["fechaIso"], reverse=True)
        _DNI_BY_NAME = {}
        for r in rows:
            nombre = (r.get("reporter_name") or "").strip()
            dni = (r.get("dni") or "").strip()
            if nombre and dni:
                _DNI_BY_NAME.setdefault(nombre, dni)
        print(f"[store] {len(_TICKETS)} tickets cargados en memoria.")


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------
def all_tickets():
    with _LOCK:
        return list(_TICKETS)


def tickets_by_dni(dni):
    dni = str(dni).strip()
    with _LOCK:
        return [t for t in _TICKETS if t["ownerDni"] == dni]


def name_for_dni(dni):
    """Devuelve el nombre del primer ciudadano con ese DNI, o None."""
    dni = str(dni).strip()
    with _LOCK:
        for t in _TICKETS:
            if t["ownerDni"] == dni:
                return t["nombre"]
    return None


def location_tree():
    """Árbol departamento -> provincia -> [distritos] a partir de los datos reales."""
    tree = {}
    with _LOCK:
        for t in _TICKETS:
            d, p, ds = t["departamento"], t["provincia"], t["distrito"]
            if not (d and p and ds):
                continue
            tree.setdefault(d, {}).setdefault(p, set()).add(ds)
    return {d: {p: sorted(v) for p, v in provs.items()} for d, provs in sorted(tree.items())}


def next_codigo():
    """Siguiente código TCK-AAAA-NNNNN sin colisionar con los existentes."""
    year = datetime.now().year
    mx = 0
    with _LOCK:
        for t in _TICKETS:
            c = t["codigo"]
            if c.startswith("TCK-"):
                try:
                    mx = max(mx, int(c.split("-")[-1]))
                except ValueError:
                    pass
    return f"TCK-{year}-{mx + 1:05d}"


# ---------------------------------------------------------------------------
# Escritura
# ---------------------------------------------------------------------------
def _display_to_row(ticket, extra):
    """Construye una fila CSV (esquema completo) desde un ticket + datos crudos."""
    row = {col: "" for col in _FIELDNAMES}
    row.update({
        "unique_key": ticket["codigo"],
        "created_date": extra["created_date"],
        "descriptor_raw": ticket["descripcion"],
        "descriptor_len": len(ticket["descripcion"]),
        "complaint_type": extra["complaint_type"],   # etiqueta cruda del modelo
        "priority": extra["priority"],                # etiqueta cruda del modelo
        "departamento": ticket["departamento"],
        "provincia": ticket["provincia"],
        "distrito": ticket["distrito"],
        "incident_address": "",
        "reporter_name": ticket["nombre"],
        "reporter_email": ticket["correo"],
        "reporter_phone": ticket["celular"],
        "sector": extra["sector_code"],
        "open_data_channel_type": "WEB",
        "attachment_count": extra["attachment_count"],
        "acepta_politica_privacidad": "1",
        "status": C.ESTADO_INICIAL,
        "dni": ticket["ownerDni"],
        "confianza": ticket["confianza"] if ticket["confianza"] is not None else "",
        "evidencia": ticket["evidenciaLabel"],
    })
    return row


def add_report(*, descripcion, nombre, correo, celular, sector_code,
               departamento, provincia, distrito, dni,
               complaint_type, priority, confianza, evidencia_label, attachment_count):
    """Crea un ticket nuevo, lo persiste en el CSV y lo devuelve listo para el front."""
    with _LOCK:
        codigo = next_codigo()
        now = datetime.now()
        ticket = {
            "codigo": codigo,
            "fechaIso": now.strftime("%Y-%m-%d"),
            "fechaFmt": _fmt_fecha(now),
            "departamento": departamento, "provincia": provincia, "distrito": distrito,
            "ubicacion": ", ".join([x for x in (distrito, provincia, departamento) if x]),
            "nombre": nombre, "correo": correo, "celular": celular,
            "sector": C.SECTOR_LABELS.get(sector_code, sector_code),
            "descripcion": descripcion,
            "area": C.AREA_LABELS.get(complaint_type, complaint_type),
            "gravedad": C.GRAVEDAD_LABELS.get(priority.upper(), "NA"),
            "estado": C.ESTADO_LABELS[C.ESTADO_INICIAL],
            "confianza": confianza,
            "evidenciaLabel": evidencia_label or "Sin evidencia adjunta",
            "ownerDni": str(dni),
        }
        extra = {
            "created_date": now.strftime("%d/%m/%Y %H:%M"),
            "complaint_type": complaint_type,
            "priority": priority.upper(),
            "sector_code": sector_code,
            "attachment_count": attachment_count,
        }
        row = _display_to_row(ticket, extra)
        with open(C.PERSIST_CSV, "a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=_FIELDNAMES, delimiter=C.CSV_DELIM)
            writer.writerow(row)
        _TICKETS.insert(0, ticket)
        return ticket


def update_estado(codigo, estado_label):
    """Cambia el estado de un ticket (admin) y lo reescribe en el CSV."""
    estado_code = next((k for k, v in C.ESTADO_LABELS.items() if v == estado_label), None)
    if estado_code is None:
        return False
    with _LOCK:
        found = False
        for t in _TICKETS:
            if t["codigo"] == codigo:
                t["estado"] = estado_label
                found = True
                break
        if not found:
            return False
        # reescritura completa del CSV con el estado actualizado
        with open(C.PERSIST_CSV, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter=C.CSV_DELIM)
            rows = list(reader)
        for r in rows:
            if (r.get("unique_key") or "").strip() == codigo:
                r["status"] = estado_code
        with open(C.PERSIST_CSV, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=_FIELDNAMES, delimiter=C.CSV_DELIM)
            writer.writeheader()
            writer.writerows(rows)
        return True
