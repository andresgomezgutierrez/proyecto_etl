"""
Módulo de Extracción - Pipeline ETL SIVIGILA
=============================================
Escanea dinámicamente todos los archivos BD-*.xlsx en la carpeta de datos
crudos de eventos de salud pública (SIVIGILA).

Retorna una lista de tuplas (DataFrame, nombre_tabla) para que cada archivo
se procese, transforme y cargue en su propia tabla MySQL.

"""

import os
import re
import glob
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# Ruta raíz donde están las carpetas por evento (cada una con BD-*.xlsx)
RUTA_DATOS_CRUDOS = os.getenv(
    "RUTA_DATOS_CRUDOS",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "raw")
)


def escanear_archivos(ruta_raiz: str) -> list:
    """
    Escanea recursivamente la ruta raíz buscando archivos que coincidan
    con el patrón BD-*.xlsx (las bases de datos crudas de SIVIGILA).
    Excluye archivos temporales de Excel (~$*) y copias.

    Args:
        ruta_raiz: Ruta al directorio raíz con las carpetas de eventos.

    Returns:
        Lista de rutas absolutas a los archivos BD-*.xlsx encontrados.
    """
    patron = os.path.join(ruta_raiz, "**", "BD-*.xlsx")
    archivos = glob.glob(patron, recursive=True)

    # Filtrar archivos temporales de Excel y copias de seguridad
    archivos = [
        f for f in archivos
        if not os.path.basename(f).startswith("~$")
        and "Copia de" not in f
    ]

    archivos.sort()
    print(f"  -> Se encontraron {len(archivos)} archivos BD-*.xlsx")
    return archivos


def generar_nombre_tabla(ruta_archivo: str) -> str:
    """
    Genera un nombre de tabla MySQL válido a partir del nombre del archivo.
    Ejemplo: BD-210-220.xlsx -> evento_210_220
             BD-813.xlsx     -> evento_813
             BD-875.xlsx     -> evento_875

    Args:
        ruta_archivo: Ruta al archivo .xlsx.

    Returns:
        Nombre de tabla sanitizado para MySQL.
    """
    nombre = os.path.basename(ruta_archivo)       # BD-210-220.xlsx
    nombre = os.path.splitext(nombre)[0]          # BD-210-220
    nombre = nombre.replace("BD-", "")            # 210-220
    nombre = re.sub(r"[^a-zA-Z0-9]", "_", nombre)  # 210_220
    nombre = nombre.strip("_").lower()            # 210_220
    return f"evento_{nombre}"


def leer_archivo_xlsx(ruta_archivo: str) -> pd.DataFrame:
    """
    Lee un archivo .xlsx de SIVIGILA y retorna un DataFrame.
    Detecta automáticamente la hoja que contiene los datos (busca 'cod_eve').
    Agrega columnas de trazabilidad (archivo y carpeta de origen).

    Args:
        ruta_archivo: Ruta absoluta al archivo .xlsx.

    Returns:
        DataFrame con los datos del archivo.
    """
    try:
        nombre_archivo = os.path.basename(ruta_archivo)
        carpeta_evento = os.path.basename(os.path.dirname(ruta_archivo))

        # Usar openpyxl directamente para elegir la hoja correcta (sin cargar data)
        import openpyxl
        wb_check = openpyxl.load_workbook(ruta_archivo, read_only=True)
        mejor_hoja = None
        max_cols = 0
        for ws_name in wb_check.sheetnames:
            ws = wb_check[ws_name]
            # Leer solo la primera fila (headers)
            first_row = next(ws.iter_rows(min_row=1, max_row=1), None)
            if first_row:
                headers = [str(c.value).lower().strip() for c in first_row if c.value]
                if "cod_eve" in headers:
                    mejor_hoja = ws_name
                    break
                if len(headers) > max_cols:
                    max_cols = len(headers)
                    mejor_hoja = ws_name
        wb_check.close()

        # Leer solo la hoja seleccionada
        df = pd.read_excel(
            ruta_archivo, engine="openpyxl",
            sheet_name=mejor_hoja, dtype=str
        )

        # Agregar metadatos de trazabilidad
        df["archivo_origen"] = nombre_archivo
        df["carpeta_evento"] = carpeta_evento

        print(f"    [OK] {carpeta_evento}/{nombre_archivo} "
              f"[{mejor_hoja}]: "
              f"{df.shape[0]} filas x {df.shape[1]} columnas")
        return df

    except Exception as e:
        print(f"    [ERROR] No se pudo leer {ruta_archivo}: {e}")
        return pd.DataFrame()


def extraer_datos() -> list:
    """
    Función principal de extracción.
    Escanea todos los archivos BD-*.xlsx y retorna una lista de tuplas
    (DataFrame, nombre_tabla) para que cada archivo se cargue en su
    propia tabla MySQL.

    Returns:
        Lista de tuplas (pd.DataFrame, str) donde str es el nombre
        de la tabla destino.
    """
    print("=" * 60)
    print("FASE 1: EXTRACCIÓN DE DATOS")
    print("=" * 60)
    print(f"Ruta de datos crudos: {RUTA_DATOS_CRUDOS}")

    # 1. Escanear archivos
    archivos = escanear_archivos(RUTA_DATOS_CRUDOS)

    if not archivos:
        raise FileNotFoundError(
            f"No se encontraron archivos BD-*.xlsx en: {RUTA_DATOS_CRUDOS}"
        )

    # 2. Leer cada archivo y generar nombre de tabla
    print("\nLeyendo archivos:")
    resultados = []
    for archivo in archivos:
        df = leer_archivo_xlsx(archivo)
        if not df.empty:
            nombre_tabla = generar_nombre_tabla(archivo)
            resultados.append((df, nombre_tabla, archivo))

    if not resultados:
        raise ValueError("No se pudieron leer datos de ningún archivo.")

    print(f"\n  -> Total: {len(resultados)} archivos leídos exitosamente")
    total_filas = sum(df.shape[0] for df, _, _ in resultados)
    print(f"  -> Total de registros: {total_filas}")

    return resultados


if __name__ == "__main__":
    resultados = extraer_datos()
    print("\nArchivos y tablas destino:")
    for df, nombre_tabla, ruta in resultados:
        print(f"  {nombre_tabla}: {df.shape[0]} filas x {df.shape[1]} columnas")
