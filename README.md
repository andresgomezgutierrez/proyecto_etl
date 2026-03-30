# Pipeline ETL - Vigilancia Epidemiologica SIVIGILA (Tolima)

**Proyecto:** Sistema de Analitica Predictiva para Vigilancia Epidemiologica mediante Integracion de Datos SIVIGILA y DANE - Caso Tolima

**Autor:** Wilson Andres Gomez Gutierrez

**Asignatura:** ETL - Maestria en Inteligencia Artificial y Ciencia de Datos

---

## Descripcion

Pipeline ETL (Extraccion, Transformacion y Carga) que procesa las bases de datos de eventos de interes en salud publica del sistema SIVIGILA (Sistema de Vigilancia en Salud Publica de Colombia), filtrando exclusivamente los datos del departamento del Tolima.

El sistema lee archivos Excel (.xlsx) con la nomenclatura `BD-*.xlsx`, aplica transformaciones de limpieza, anonimizacion y filtrado geografico inteligente, y carga los datos en una base de datos MySQL donde **cada evento genera su propia tabla**.

### Caracteristicas principales

- **Escaneo dinamico:** Detecta automaticamente todos los archivos `BD-*.xlsx` en la carpeta `data/raw/`.
- **Auto-deteccion de hoja:** En archivos Excel con multiples hojas, selecciona automaticamente la que contiene datos SIVIGILA (busca la columna `cod_eve`).
- **Filtrado geografico inteligente:**
  - Eventos ETV/Zoonosis (dengue, leishmaniasis, leptospirosis, etc.): filtran por **PROCEDENCIA** (`cod_dpto_o`), ya que el lugar de ocurrencia es epidemiologicamente relevante.
  - Demas eventos (cronicos, materno-perinatales, salud mental, etc.): filtran por **RESIDENCIA** (`cod_dpto_r`), ya que la entidad territorial responde por sus residentes.
- **Anonimizacion de PII:** Elimina nombres, documentos de identidad, direcciones, telefonos y coordenadas.
- **Full Reload:** Cada ejecucion borra y recrea las tablas (DROP + CREATE + INSERT) porque los epidemiologos pueden modificar registros historicos durante las unidades de analisis.
- **Una tabla por evento:** Cada archivo BD genera su propia tabla en MySQL (ej. `evento_210_220`, `evento_813`).
- **API REST con FastAPI:** Endpoints para consultar los datos procesados.
- **Respaldo CSV:** Guarda archivos CSV procesados como respaldo independiente de MySQL.

---

## Estructura del Proyecto

```
etl_2026/
├── README.md                  # Este archivo
├── requirements.txt           # Dependencias de Python
├── .env                       # Variables de entorno (conexion MySQL, rutas)
├── src/
│   ├── extract.py             # Fase 1: Extraccion de archivos BD-*.xlsx
│   ├── transform.py           # Fase 2: Transformacion, filtrado y anonimizacion
│   ├── load.py                # Fase 3: Carga a MySQL (Full Reload)
│   └── pipeline.py            # Orquestador principal del ETL
├── api/
│   └── main.py                # API REST con FastAPI
└── data/
    ├── raw/                   # Archivos originales BD-*.xlsx (50 archivos)
    └── processed/             # CSVs procesados y graficas de reporte
```

---

## Requisitos Previos

- Python 3.9 o superior
- MySQL Server 8.0 o superior
- pip (gestor de paquetes de Python)

---

## Instalacion

### 1. Clonar o copiar el proyecto

```bash
cd etl_2026
```

### 2. Crear entorno virtual (recomendado)

```bash
python -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

Editar el archivo `.env` en la raiz del proyecto:

```env
# Conexion a MySQL
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=tu_contraseña
DB_NAME=sivigila_tolima
```

> **Nota:** Si `RUTA_DATOS_CRUDOS` no esta definida, el pipeline busca automaticamente en `data/raw/` dentro del proyecto.

### 5. Configurar MySQL

Crear la base de datos (el pipeline la crea automaticamente si el usuario tiene permisos):

```sql
CREATE DATABASE IF NOT EXISTS sivigila_tolima
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

---

## Uso

### Ejecutar el pipeline ETL completo

```bash
cd src
python pipeline.py
```

El pipeline ejecutara secuencialmente:

1. **Extraccion:** Escanea y lee los 50 archivos BD-*.xlsx de `data/raw/`.
2. **Transformacion:** Normaliza columnas, anonimiza PII, filtra por Tolima (cod_dpto = 73) con criterio inteligente de procedencia/residencia, convierte tipos de datos y elimina duplicados.
3. **Carga:** Guarda respaldos CSV en `data/processed/` y carga cada evento en su propia tabla MySQL con estrategia Full Reload.

### Ejecutar modulos individuales

```bash
# Solo extraccion (verificar lectura de archivos)
python extract.py

# Solo transformacion de prueba (3 primeros archivos)
python transform.py

# Probar conexion a MySQL
python load.py
```

### Iniciar la API REST

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

La documentacion interactiva estara disponible en: `http://localhost:8000/docs`

---

## Endpoints de la API

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/` | Estado de la API |
| GET | `/tablas` | Listar todos los eventos/tablas disponibles con conteo de registros |
| GET | `/datos/{nombre_tabla}` | Consultar registros con paginacion (`limite`, `offset`, `anio`) |
| GET | `/datos/{nombre_tabla}/todos` | Obtener todos los registros de un evento |
| GET | `/datos/{nombre_tabla}/columnas` | Listar columnas de una tabla |
| GET | `/resumen` | Resumen estadistico global de todos los eventos |

### Ejemplos de consulta

```bash
# Listar tablas disponibles
curl http://localhost:8000/tablas

# Consultar 10 registros de dengue
curl "http://localhost:8000/datos/evento_210_220?limite=10"

# Filtrar tuberculosis por año
curl "http://localhost:8000/datos/evento_813?anio=2024"

# Resumen global
curl http://localhost:8000/resumen
```

---

## Eventos Procesados

El pipeline procesa aproximadamente 50 archivos de eventos de salud publica agrupados en ~41 tablas unicas. Algunos ejemplos:

| Codigo | Evento | Tabla MySQL | Criterio de Filtro |
|--------|--------|-------------|-------------------|
| 210/220 | Dengue / Dengue Grave | `evento_210_220` | Procedencia |
| 580 | Mortalidad por Dengue | `evento_580` | Procedencia |
| 420/430/440 | Leishmaniasis | `evento_420_430_440` | Procedencia |
| 455 | Leptospirosis | `evento_455` | Procedencia |
| 895 | Zika | `evento_895` | Procedencia |
| 217 | Chikungunya | `evento_217` | Procedencia |
| 355 | ETA | `evento_355` | Procedencia |
| 356 | Intento de Suicidio | `evento_356` | Residencia |
| 813 | Tuberculosis | `evento_813` | Residencia |
| 850 | VIH/SIDA | `evento_850` | Residencia |
| 875 | Violencia de Genero | `evento_875` | Residencia |
| 110 | Bajo Peso al Nacer | `evento_110` | Residencia |
| 995 | IRA (Infeccion Resp. Aguda) | `evento_995` | Residencia |
| 998 | EDA (Enf. Diarreica Aguda) | `evento_998` | Residencia |

---

## Estrategia de Carga: Full Reload

Cada ejecucion del pipeline realiza un **Full Reload** (borrar y recargar) por cada tabla:

```
DROP TABLE IF EXISTS evento_XXX  ->  CREATE TABLE evento_XXX  ->  INSERT (lotes de 1000)
```

**Justificacion:** En SIVIGILA no existen variables de control de edicion. Los epidemiologos pueden modificar registros historicos al realizar unidades de analisis (por ejemplo, actualizar la causa de muerte de un caso de tuberculosis antiguo despues de una junta medica). Por lo tanto, no es posible aplicar una estrategia incremental y se requiere recargar toda la informacion en cada ejecucion.

---

## Filtrado Geografico Inteligente

El filtrado para el departamento del Tolima (codigo DANE 73) se aplica de forma diferenciada segun el tipo de evento, siguiendo los protocolos de vigilancia del INS (Instituto Nacional de Salud):

**Por Procedencia (cod_dpto_o):** Eventos ETV (Enfermedades Transmitidas por Vectores) y Zoonosis. El lugar de procedencia/ocurrencia indica donde el paciente adquirio la enfermedad o se expuso al vector/animal.

**Por Residencia (cod_dpto_r):** Todos los demas eventos (cronicos, materno-perinatales, salud mental, inmunoprevenibles, etc.). La entidad territorial es responsable de la salud de sus residentes.

El sistema incluye un mecanismo de fallback para archivos con columnas diferentes: si la columna principal no existe, intenta alternativas conocidas o deriva el departamento desde el codigo de municipio (`cod_mun[:2]`).

---

## Anonimizacion

Para cumplir con la proteccion de datos personales en salud, el pipeline elimina las siguientes columnas PII (Datos Personales Identificables):

- Nombres y apellidos (`pri_nom_`, `seg_nom_`, `pri_ape_`, `seg_ape_`)
- Documento de identidad (`num_ide_`, `tip_ide_`)
- Direccion y barrio (`dir_res_`, `bar_ver_`)
- Telefono (`telefono_`)
- Datos del diligenciador (`nom_dil_f_`, `tel_dil_f_`)
- Coordenadas GPS (`lat_dir`, `long_dir`)

---

## Dependencias

```
pandas>=2.0.0
openpyxl>=3.1.0
numpy>=1.24.0
matplotlib>=3.7.0
mysql-connector-python>=8.0.0
python-dotenv>=1.0.0
fastapi>=0.100.0
uvicorn>=0.23.0
```

---

## Notas Tecnicas

- Los archivos duplicados (mismo BD-*.xlsx en carpetas diferentes) se fusionan automaticamente en una sola tabla, eliminando registros duplicados.
- El pipeline libera memoria progresivamente con `gc.collect()` para manejar archivos grandes.
- La API lee desde los CSV procesados en `data/processed/`, por lo que funciona independientemente de MySQL.
- Los inserts a MySQL se realizan en lotes de 1000 registros para eficiencia.
- Si MySQL no esta disponible, el pipeline guarda los datos en CSV como respaldo.
