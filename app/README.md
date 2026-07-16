# Sistema NLP · Reportes Ciudadanos (PE-311)

Despliegue local que conecta el diseño del front con los **dos modelos BETO ya
entrenados** (`pesos/`) y con una **persistencia en CSV**.

## Arranque rápido

Desde la raíz del repositorio:

```powershell
# Windows
.\run.ps1
```

```bash
# Linux / Mac
bash run.sh
```

El script crea un entorno virtual, instala dependencias (Flask, torch CPU,
transformers) y levanta el servidor en **http://127.0.0.1:5000**.

> Los modelos ya están entrenados en `pesos/`. **No se reentrena nada**; el
> notebook solo queda como referencia.

### Arranque manual (si ya tienes las dependencias)

```bash
cd app
python server.py
```

## Cómo probarlo

1. Abre http://127.0.0.1:5000
2. **Ciudadano**: ingresa un DNI del padrón (empiezan en `4000`) o uno nuevo.
   - *Nuevo reporte*: llena el formulario y describe el incidente. Al enviar,
     el modelo BETO clasifica **área** (tipo) y **gravedad** (prioridad) y se
     guarda en el CSV de persistencia con tu DNI.
   - *Mis solicitudes*: muestra los reportes asociados a tu DNI.
3. **Administrador**: ingresa cualquier DNI (demo `99999999`).
   - *Dashboard*: KPIs, series temporales, ranking de áreas, mapa por departamento.
   - *Tickets*: tabla filtrable; abre un ticket para cambiar su estado (se persiste).

## Arquitectura

| Archivo | Rol |
|---|---|
| `server.py` | API Flask + sirve el front |
| `ml.py` | Carga los modelos BETO (tipo + prioridad) y clasifica. Fallback por palabras clave si faltan pesos/torch |
| `store.py` | Persistencia CSV, asignación de DNI, alta/consulta de tickets |
| `config.py` | Rutas y **mapeos del cruce de datos** (código dataset → etiqueta legible) |
| `static/index.html` | Front funcional (SPA) que consume la API |
| `data/pe311_entrenamiento.csv` | Copia intacta para reentrenar (se genera al arrancar) |
| `data/pe311_persistencia.csv` | Copia + columna `dni` sobre la que se lee/escribe |

## Datos y DNI

- En el **primer arranque** se generan dos copias del dataset en `app/data/`.
- A cada **nombre único** se le asigna un DNI incremental empezando en `4000`.
  Si un nombre se repite, comparte DNI (riesgo asumido, como se acordó).
- Los reportes creados desde el formulario se guardan con el DNI del ciudadano
  en sesión y quedan disponibles en "Mis solicitudes".
- Para regenerar todo desde cero, borra la carpeta `app/data/`.

## Notas del cruce de datos (dataset ↔ diseño)

- **Área derivada** = `complaint_type` del modelo (8 clases reales), con etiquetas
  legibles. Reemplaza a las 7 áreas ficticias del diseño original.
- **Gravedad** = `priority` del modelo (ALTA/MEDIA/BAJA → Alta/Media/Baja).
- **Estado** usa los 6 estados reales del dataset (Recibido, Asignado, En proceso,
  Derivado, Cerrado, Rechazado).
- **Ubicación** (departamento/provincia/distrito) se arma del dataset real.
- **DNI**: el diseño pedía 8 dígitos; como los DNI del padrón empiezan en 4000
  (4 dígitos), el login acepta de 3 a 8 dígitos.
