from fastapi import FastAPI, HTTPException
import pandas as pd
import numpy as np
from pathlib import Path


app = FastAPI(title="API ETL 2026")

BASE_DIR = Path(__file__).resolve().parent.parent
RUTA_CSV = BASE_DIR / "data" / "processed" / "datos_finales.csv"


def limpiar_para_json(df: pd.DataFrame):
    df = df.copy()

    # Reemplaza inf y -inf por NaN
    df = df.replace([np.inf, -np.inf], np.nan)

    # Reemplaza NaN por None
    df = df.astype(object).where(pd.notnull(df), None)

    return df


@app.get("/")
def inicio():
    return {"mensaje": "API funcionando correctamente"}


@app.get("/datos")
def obtener_datos(limite: int = 10):
    if not RUTA_CSV.exists():
        raise HTTPException(status_code=404, detail="No existe el archivo datos_finales.csv")

    df = pd.read_csv(RUTA_CSV)
    df = limpiar_para_json(df)

    return {
        "total_registros": len(df),
        "datos_mostrados": min(limite, len(df)),
        "datos": df.head(limite).to_dict(orient="records")
    }


@app.get("/datos/todos")
def obtener_todos_los_datos():
    if not RUTA_CSV.exists():
        raise HTTPException(status_code=404, detail="No existe el archivo datos_finales.csv")

    df = pd.read_csv(RUTA_CSV)
    df = limpiar_para_json(df)

    return {
        "total_registros": len(df),
        "datos": df.to_dict(orient="records")
    }


@app.get("/columnas")
def obtener_columnas():
    if not RUTA_CSV.exists():
        raise HTTPException(status_code=404, detail="No existe el archivo datos_finales.csv")

    df = pd.read_csv(RUTA_CSV)

    return {
        "columnas": df.columns.tolist()
    }