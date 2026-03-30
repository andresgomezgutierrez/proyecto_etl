"""
API REST - Pipeline ETL SIVIGILA (Tolima)
==========================================
API construida con FastAPI para servir los datos procesados.
Cada evento tiene su propio CSV y tabla MySQL.

Endpoints:
  GET /              -> Estado de la API
  GET /tablas        -> Listar tablas/eventos disponibles
  GET /datos/{tabla} -> Consultar registros de una tabla específica
  GET /resumen       -> Resumen estadístico global

Autor: Wilson Andrés Gómez Gutiérrez
Asignatura: ETL - Maestría en IA y Ciencia de Datos
"""

from fastapi import FastAPI, HTTPException, Query
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional

app = FastAPI(
    title="API ETL SIVIGILA - Tolima",
    description="API para consultar datos procesados de vigilancia "
                "epidemiológica del departamento del Tolima. "
                "Cada evento tiene su propia tabla.",
    version="2.0.0",
)

BASE_DIR = Path(__file__).resolve().parent.parent
RUTA_PROCESADOS = BASE_DIR / "data" / "processed"


def listar_csvs() -> dict:
    """Retorna un dict {nombre_tabla: ruta_csv} de los CSVs disponibles."""
    if not RUTA_PROCESADOS.exists():
        return {}
    csvs = {}
    for f in sorted(RUTA_PROCESADOS.glob("evento_*.csv")):
        nombre = f.stem  # evento_210_220
        csvs[nombre] = f
    return csvs


def cargar_csv(nombre_tabla: str) -> pd.DataFrame:
    """Carga un CSV por nombre de tabla."""
    csvs = listar_csvs()
    if nombre_tabla not in csvs:
        raise HTTPException(
            status_code=404,
            detail=f"Tabla '{nombre_tabla}' no encontrada. "
                   f"Tablas disponibles: {list(csvs.keys())}"
        )
    return pd.read_csv(csvs[nombre_tabla], low_memory=False)


def limpiar_para_json(df: pd.DataFrame) -> pd.DataFrame:
    """Limpia valores no serializables para JSON."""
    df = df.copy()
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.astype(object).where(pd.notnull(df), None)
    return df


@app.get("/")
def inicio():
    """Estado de la API."""
    csvs = listar_csvs()
    return {
        "mensaje": "API ETL SIVIGILA - Tolima funcionando correctamente",
        "tablas_disponibles": len(csvs),
        "version": "2.0.0 - Una tabla por evento"
    }


@app.get("/tablas")
def obtener_tablas():
    """Lista todas las tablas/eventos disponibles con su conteo."""
    csvs = listar_csvs()
    if not csvs:
        raise HTTPException(
            status_code=404,
            detail="No hay datos procesados. Ejecute primero el pipeline."
        )

    tablas = []
    for nombre, ruta in csvs.items():
        try:
            df = pd.read_csv(ruta, nrows=1)
            n_filas = sum(1 for _ in open(ruta)) - 1  # Contar líneas sin cargar
            tablas.append({
                "nombre_tabla": nombre,
                "registros": n_filas,
                "columnas": len(df.columns),
            })
        except Exception:
            tablas.append({
                "nombre_tabla": nombre,
                "registros": "error",
                "columnas": "error",
            })

    return {"total_tablas": len(tablas), "tablas": tablas}


@app.get("/datos/{nombre_tabla}")
def obtener_datos(
    nombre_tabla: str,
    limite: int = Query(default=10, ge=1, le=10000),
    offset: int = Query(default=0, ge=0),
    anio: Optional[int] = Query(default=None, description="Filtrar por año"),
):
    """Consulta registros de una tabla/evento específico."""
    df = cargar_csv(nombre_tabla)

    if anio is not None and "año" in df.columns:
        df = df[df["año"] == anio]

    total = len(df)
    df_page = df.iloc[offset:offset + limite]
    df_page = limpiar_para_json(df_page)

    return {
        "tabla": nombre_tabla,
        "total_registros": total,
        "offset": offset,
        "limite": limite,
        "datos_mostrados": len(df_page),
        "datos": df_page.to_dict(orient="records")
    }


@app.get("/datos/{nombre_tabla}/todos")
def obtener_todos(nombre_tabla: str):
    """Retorna todos los registros de una tabla."""
    df = cargar_csv(nombre_tabla)
    df = limpiar_para_json(df)
    return {
        "tabla": nombre_tabla,
        "total_registros": len(df),
        "datos": df.to_dict(orient="records")
    }


@app.get("/datos/{nombre_tabla}/columnas")
def obtener_columnas(nombre_tabla: str):
    """Retorna las columnas de una tabla."""
    df = cargar_csv(nombre_tabla)
    return {
        "tabla": nombre_tabla,
        "total_columnas": len(df.columns),
        "columnas": df.columns.tolist()
    }


@app.get("/resumen")
def obtener_resumen():
    """Resumen estadístico global de todos los eventos."""
    csvs = listar_csvs()

    resumen_tablas = []
    total_registros = 0

    for nombre, ruta in csvs.items():
        try:
            df = pd.read_csv(ruta, low_memory=False)
            info = {
                "tabla": nombre,
                "registros": len(df),
                "columnas": len(df.columns),
            }
            if "nom_eve" in df.columns:
                info["evento"] = df["nom_eve"].iloc[0] if len(df) > 0 else None
            if "año" in df.columns:
                info["años"] = sorted(df["año"].dropna().astype(int).unique().tolist())

            resumen_tablas.append(info)
            total_registros += len(df)
        except Exception as e:
            resumen_tablas.append({"tabla": nombre, "error": str(e)})

    return {
        "total_tablas": len(csvs),
        "total_registros_global": total_registros,
        "tablas": resumen_tablas
    }
