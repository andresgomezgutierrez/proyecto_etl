"""
Módulo de Carga - Pipeline ETL SIVIGILA
========================================
Carga los datos transformados a una base de datos MySQL.
Crea una tabla independiente por cada archivo/evento de SIVIGILA.

Estrategia: FULL RELOAD (TRUNCATE + INSERT) por tabla.
Justificación: Los epidemiólogos pueden modificar registros históricos
al realizar unidades de análisis y no existen variables de control de
edición en SIVIGILA.

La configuración de conexión se gestiona mediante variables de entorno (.env).

"""

import os
import re
import pandas as pd
import numpy as np
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

# ─── Configuración de conexión desde .env ──────────────────────────────
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "sivigila_tolima")


def map_dtype(serie: pd.Series) -> str:
    """Mapea tipos de datos de Pandas a tipos MySQL."""
    if pd.api.types.is_datetime64_any_dtype(serie):
        return "DATETIME"
    elif pd.api.types.is_integer_dtype(serie):
        return "INT"
    elif pd.api.types.is_float_dtype(serie):
        return "FLOAT"
    elif pd.api.types.is_bool_dtype(serie):
        return "TINYINT"
    else:
        max_len = serie.dropna().astype(str).str.len().max()
        if pd.isna(max_len) or max_len == 0:
            return "VARCHAR(255)"
        elif max_len <= 50:
            return "VARCHAR(50)"
        elif max_len <= 255:
            return "VARCHAR(255)"
        else:
            return "TEXT"


def sanitizar_nombre_columna(nombre: str) -> str:
    """Sanitiza un nombre de columna para que sea válido en MySQL."""
    nombre = re.sub(r"[^a-zA-Z0-9_]", "_", nombre)
    nombre = nombre.strip("_")[:64]
    if not nombre:
        nombre = "col_sin_nombre"
    return nombre


def obtener_conexion():
    """Establece conexión a MySQL."""
    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4",
        collation="utf8mb4_unicode_ci",
    )


def crear_base_datos_si_no_existe():
    """Crea la base de datos si no existe."""
    try:
        conn = mysql.connector.connect(
            host=DB_HOST, port=DB_PORT,
            user=DB_USER, password=DB_PASSWORD,
        )
        cursor = conn.cursor()
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
            f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        cursor.close()
        conn.close()
        print(f"  -> Base de datos `{DB_NAME}` verificada/creada.")
    except Exception as e:
        print(f"  -> ADVERTENCIA: No se pudo crear la BD: {e}")


def guardar_csv_individual(df: pd.DataFrame, nombre_tabla: str, ruta_salida: str):
    """Guarda un CSV de respaldo por cada tabla/evento."""
    os.makedirs(ruta_salida, exist_ok=True)
    ruta_csv = os.path.join(ruta_salida, f"{nombre_tabla}.csv")
    df.to_csv(ruta_csv, index=False, encoding="utf-8-sig")
    return ruta_csv


def cargar_tabla(df: pd.DataFrame, nombre_tabla: str, conn):
    """
    Carga un DataFrame en una tabla MySQL específica.
    Estrategia FULL RELOAD: DROP + CREATE + INSERT.

    Se usa DROP + CREATE en vez de TRUNCATE para manejar cambios
    de esquema (columnas que se agregan o eliminan entre ejecuciones).

    Args:
        df: DataFrame limpio listo para cargar.
        nombre_tabla: Nombre de la tabla destino en MySQL.
        conn: Conexión MySQL activa.

    Returns:
        int: Número de registros insertados.
    """
    cursor = conn.cursor()

    try:
        # 1. DROP tabla si existe (para manejar cambios de esquema)
        cursor.execute(f"DROP TABLE IF EXISTS `{nombre_tabla}`")

        # 2. CREATE tabla con las columnas del DataFrame actual
        definiciones = []
        columnas_safe = []
        for col in df.columns:
            col_safe = sanitizar_nombre_columna(col)
            columnas_safe.append(col_safe)
            tipo_mysql = map_dtype(df[col])
            definiciones.append(f"`{col_safe}` {tipo_mysql}")

        create_query = f"""
        CREATE TABLE `{nombre_tabla}` (
            id INT AUTO_INCREMENT PRIMARY KEY,
            {", ".join(definiciones)}
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
        cursor.execute(create_query)

        # 3. Preparar datos para inserción
        df_insert = df.copy()
        for col in df_insert.select_dtypes(include=["datetime64"]).columns:
            df_insert[col] = df_insert[col].dt.strftime("%Y-%m-%d %H:%M:%S")

        df_insert = df_insert.replace([np.inf, -np.inf], np.nan)
        df_insert = df_insert.astype(object).where(pd.notnull(df_insert), None)

        # 4. INSERT en lotes
        columnas_sql = ", ".join([f"`{c}`" for c in columnas_safe])
        placeholders = ", ".join(["%s"] * len(columnas_safe))
        insert_query = f"INSERT INTO `{nombre_tabla}` ({columnas_sql}) VALUES ({placeholders})"

        data = [
            tuple(None if pd.isna(v) else v for v in fila)
            for fila in df_insert.itertuples(index=False, name=None)
        ]

        batch_size = 1000
        total = 0
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            cursor.executemany(insert_query, batch)
            total += len(batch)

        conn.commit()
        return total

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()


def carga_datos(lista_transformados: list):
    """
    Función principal de carga.
    Recibe una lista de tuplas (DataFrame, nombre_tabla) y carga
    cada una en su propia tabla MySQL con estrategia FULL RELOAD.

    También guarda un CSV de respaldo por cada tabla.

    Args:
        lista_transformados: Lista de tuplas (pd.DataFrame, str).
    """
    print("\n" + "=" * 60)
    print("FASE 3: CARGA DE DATOS (FULL RELOAD - UNA TABLA POR EVENTO)")
    print("=" * 60)

    ruta_csv = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "data", "processed"
    )

    # 1. Guardar CSVs de respaldo
    print("\n  Guardando respaldos CSV...")
    tablas_validas = []
    for df, nombre_tabla in lista_transformados:
        if df.empty:
            print(f"    [SKIP] {nombre_tabla}: sin datos (0 registros)")
            continue
        csv_path = guardar_csv_individual(df, nombre_tabla, ruta_csv)
        tablas_validas.append((df, nombre_tabla))
        print(f"    [CSV] {nombre_tabla}: {df.shape[0]} filas -> {csv_path}")

    if not tablas_validas:
        print("\n  No hay datos para cargar a MySQL.")
        return

    # 2. Conexión MySQL y carga tabla por tabla
    print(f"\n  Conectando a MySQL ({DB_HOST}:{DB_PORT}/{DB_NAME})...")

    conn = None
    try:
        crear_base_datos_si_no_existe()
        conn = obtener_conexion()

        print(f"  -> Conexión exitosa. Cargando {len(tablas_validas)} tablas...\n")

        total_global = 0
        tablas_ok = 0
        tablas_error = 0

        for df, nombre_tabla in tablas_validas:
            try:
                n_insertados = cargar_tabla(df, nombre_tabla, conn)
                total_global += n_insertados
                tablas_ok += 1
                print(f"    [OK] {nombre_tabla}: "
                      f"{n_insertados} registros insertados "
                      f"({df.shape[1]} columnas)")
            except Exception as e:
                tablas_error += 1
                print(f"    [ERROR] {nombre_tabla}: {e}")

        print(f"\n  ─── RESUMEN DE CARGA ───")
        print(f"  Tablas cargadas:  {tablas_ok}")
        print(f"  Tablas con error: {tablas_error}")
        print(f"  Total registros:  {total_global}")

    except mysql.connector.Error as e:
        print(f"\n  [ERROR MySQL] No se pudo conectar: {e}")
        print("  -> Los datos se guardaron en los respaldos CSV.")
        print("  -> Verifica la configuración en el archivo .env")

    except Exception as e:
        print(f"\n  [ERROR] {e}")
        raise

    finally:
        try:
            if conn:
                conn.close()
                print("  -> Conexión MySQL cerrada.")
        except Exception:
            pass


if __name__ == "__main__":
    print("Probando conexión a MySQL...")
    print(f"  Host: {DB_HOST}:{DB_PORT}")
    print(f"  User: {DB_USER}")
    print(f"  Database: {DB_NAME}")
    try:
        conn = obtener_conexion()
        print("  -> Conexión exitosa!")
        conn.close()
    except Exception as e:
        print(f"  -> Error: {e}")
