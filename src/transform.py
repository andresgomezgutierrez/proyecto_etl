"""
Módulo de Transformación - Pipeline ETL SIVIGILA
=================================================
Aplica las transformaciones necesarias sobre cada DataFrame individual
de un evento SIVIGILA para obtener datos limpios, anonimizados y
listos para carga en su tabla MySQL correspondiente.

Transformaciones aplicadas:
  1. Eliminación de columnas duplicadas
  2. Normalización de nombres de columnas
  3. Estandarización de valores nulos
  4. Anonimización de PII (datos personales identificables)
  5. Filtrado geográfico inteligente:
     - Eventos ETV/Zoonosis: por PROCEDENCIA (cod_dpto_o = lugar de ocurrencia)
     - Eventos crónicos/materno-perinatales/salud mental: por RESIDENCIA (cod_dpto_r)
  6. Conversión de fechas a formato datetime
  7. Conversión de tipos numéricos
  8. Eliminación de duplicados

Referencia para clasificación por procedencia/residencia:
  Según los protocolos de vigilancia del INS, las enfermedades transmitidas
  por vectores (ETV) y zoonosis se analizan por LUGAR DE PROCEDENCIA
  (donde el paciente adquirió la enfermedad, exposición al vector/animal).
  Los demás eventos (crónicos, materno-perinatales, salud mental, ITS, etc.)
  se analizan por LUGAR DE RESIDENCIA del paciente.
  Fuentes:
    - https://www.ins.gov.co/buscador-eventos/Paginas/Fichas-y-Protocolos.aspx
    - https://www.ins.gov.co/BibliotecaDigital/lineamientos-nacionales-2022.pdf


"""

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # Backend sin GUI para servidores
import matplotlib.pyplot as plt


# ─── Columnas PII que deben eliminarse para anonimización ──────────────
COLUMNAS_PII = [
    "pri_nom_", "seg_nom_", "pri_ape_", "seg_ape_",  # Nombres
    "num_ide_", "tip_ide_",                            # Documento de identidad
    "dir_res_", "bar_ver_", "telefono_",               # Dirección y teléfono
    "nom_dil_f_", "tel_dil_f_",                        # Datos del diligenciador
    "lat_dir", "long_dir",                             # Coordenadas exactas
]

# ─── Columnas de fecha que requieren conversión a datetime ─────────────
COLUMNAS_FECHA = [
    "fec_not", "ini_sin_", "fec_con_", "fec_hos_",
    "fec_def_", "fec_aju_", "fec_arc_xl", "fecha_nto_",
]

# ─── Columnas numéricas enteras ────────────────────────────────────────
COLUMNAS_NUMERICAS_INT = [
    "cod_eve", "semana", "año", "edad_", "uni_med_",
    "sexo_", "cod_dpto_o", "cod_mun_o", "area_",
    "estrato_", "tip_cas_", "pac_hos_", "con_fin_",
    "cod_dpto_r", "cod_mun_r", "ajuste_",
]

# ─── Código DANE del Departamento del Tolima ───────────────────────────
COD_DPTO_TOLIMA = "73"

# ─── Eventos que se analizan por PROCEDENCIA (cod_dpto_o) ─────────────
# Enfermedades Transmitidas por Vectores (ETV) y Zoonosis:
# El lugar de procedencia/ocurrencia corresponde al sitio geográfico
# donde el paciente adquirió o se expuso al agente o vector.
# Fuente: Protocolos de vigilancia INS, Lineamientos Nacionales 2022.
EVENTOS_POR_PROCEDENCIA = {
    100,   # Accidente ofídico (zoonosis)
    205,   # Chagas (ETV - Tripanosomiasis americana)
    210,   # Dengue (ETV)
    220,   # Dengue grave (ETV)
    217,   # Chikungunya (ETV)
    228,   # Exposición a flúor (ambiental)
    300,   # Agresiones por animales pot. transmisores de rabia (zoonosis)
    307,   # Rabia humana (zoonosis)
    310,   # Fiebre amarilla (ETV)
    330,   # Hepatitis A (transmisión fecal-oral, asociada a fuente hídrica)
    355,   # ETA - Enfermedades transmitidas por alimentos (ambiental)
    420,   # Leishmaniasis cutánea (ETV)
    430,   # Leishmaniasis mucosa (ETV)
    440,   # Leishmaniasis visceral (ETV)
    455,   # Leptospirosis (zoonosis)
    580,   # Mortalidad por dengue (ETV)
    895,   # Zika (ETV)
}

# ─── Todos los demás eventos se analizan por RESIDENCIA (cod_dpto_r) ──
# Incluye: materno-perinatales, crónicas, salud mental, ITS, cáncer,
# enfermedades inmunoprevenibles, mortalidad infantil, etc.
# Ejemplos: 110 (Bajo peso), 113 (Desnutrición), 115/155 (Cáncer),
#   215 (Defectos congénitos), 340 (Hepatitis B/C), 342 (Huérfanas),
#   345/348 (IRAG), 356 (Intento suicidio), 365 (Intoxicaciones),
#   450 (Lepra), 452/453 (Lesiones), 535 (Meningitis),
#   549/551 (Morb/Mort materna), 560 (Mort. perinatal),
#   591 (Muertes <5 años), 610 (Parálisis flácida), 620 (Parotiditis),
#   720 (Rubéola congénita), 730/710 (Sarampión/Rubéola),
#   740 (Sífilis congénita), 750 (Sífilis gestacional),
#   800 (Tosferina), 813 (Tuberculosis), 831 (Varicela),
#   850 (VIH/SIDA), 875 (Violencia de género), 880 (Monkeypox),
#   995 (IRA), 998 (EDA), COVID-19


def normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza los nombres de las columnas: minúsculas, sin espacios."""
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
        .str.replace(".", "_", regex=False)
    )
    return df


def estandarizar_nulos(df: pd.DataFrame) -> pd.DataFrame:
    """Reemplaza distintas representaciones de nulo por np.nan."""
    valores_nulos = [
        "", "NA", "N/A", "Na", "na", "n/a", "None", "none",
        "NONE", "null", "NULL", "Desconocido", "DESCONOCIDO",
        "SD", "sd", "S/D", "s/d", "ND", "nd", "NO DATO",
    ]
    df = df.replace(valores_nulos, np.nan)
    df = df.infer_objects(copy=False)
    return df


def anonimizar_pii(df: pd.DataFrame) -> pd.DataFrame:
    """Elimina columnas PII para cumplir con protección de datos."""
    columnas_a_eliminar = [col for col in COLUMNAS_PII if col in df.columns]
    n_eliminadas = len(columnas_a_eliminar)
    df = df.drop(columns=columnas_a_eliminar)
    print(f"    Anonimización: {n_eliminadas} columnas PII eliminadas")
    return df


def determinar_criterio_filtro(df: pd.DataFrame) -> str:
    """
    Determina si el evento se debe filtrar por PROCEDENCIA (cod_dpto_o)
    o por RESIDENCIA (cod_dpto_r) según el código de evento (cod_eve).

    Los eventos ETV y zoonosis se analizan por procedencia porque el
    lugar de ocurrencia (donde el paciente se expuso al vector/animal)
    es lo epidemiológicamente relevante.

    Los demás eventos se analizan por residencia porque la entidad
    territorial es responsable de la salud de sus residentes.

    Returns:
        "procedencia" o "residencia"
    """
    if "cod_eve" not in df.columns:
        return "procedencia"  # fallback al comportamiento original

    # Obtener los códigos de evento presentes en el DataFrame
    codigos = pd.to_numeric(df["cod_eve"], errors="coerce").dropna().unique()

    # Si TODOS los códigos del archivo son de tipo ETV/zoonosis -> procedencia
    # Si al menos uno NO lo es -> residencia (enfoque conservador)
    codigos_set = set(int(c) for c in codigos if not pd.isna(c))

    if codigos_set and codigos_set.issubset(EVENTOS_POR_PROCEDENCIA):
        return "procedencia"
    else:
        return "residencia"


def filtrar_departamento(df: pd.DataFrame, cod_dpto: str = COD_DPTO_TOLIMA) -> pd.DataFrame:
    """
    Filtra registros del departamento del Tolima aplicando el criterio
    correcto según el tipo de evento:

    - Eventos ETV/Zoonosis: filtra por cod_dpto_o (PROCEDENCIA)
      Columna: departamento de ocurrencia/procedencia.
      Razón: el lugar relevante es donde se adquirió la enfermedad.

    - Demás eventos: filtra por cod_dpto_r (RESIDENCIA)
      Columna: departamento de residencia del paciente.
      Razón: la entidad territorial responde por sus residentes.
    """
    n_antes = len(df)
    criterio = determinar_criterio_filtro(df)

    if criterio == "procedencia":
        columna = "cod_dpto_o"
        etiqueta = "PROCEDENCIA (cod_dpto_o)"
    else:
        columna = "cod_dpto_r"
        etiqueta = "RESIDENCIA (cod_dpto_r)"

    if columna not in df.columns:
        # Fallback: intentar alternativas conocidas en SIVIGILA
        alternativas = [
            "cod_dpto_r", "cod_dpto_o", "cod_dpto_p",  # variantes comunes
        ]
        columna_encontrada = None
        for alt in alternativas:
            if alt in df.columns:
                columna_encontrada = alt
                break

        if columna_encontrada:
            print(f"    ADVERTENCIA: No se encontró '{columna}', "
                  f"usando '{columna_encontrada}' como alternativa.")
            columna = columna_encontrada
            etiqueta = f"ALTERNATIVA ({columna_encontrada})"
        elif "cod_mun" in df.columns or "cod_mun_" in df.columns:
            # Último recurso: derivar departamento del código de municipio
            # Los códigos DANE de municipio tienen formato DDDMM (depto + mpio)
            # Tolima = 73, entonces cod_mun empieza con 73
            col_mun = "cod_mun" if "cod_mun" in df.columns else "cod_mun_"
            print(f"    ADVERTENCIA: Sin columna de departamento. "
                  f"Derivando desde '{col_mun}' (primeros 2 dígitos).")
            df = df[
                df[col_mun].astype(str).str.strip().str[:2] == str(cod_dpto)
            ].copy()
            n_despues = len(df)
            print(f"    Filtro Tolima por MUNICIPIO ({col_mun}[:2]=={cod_dpto}): "
                  f"{n_antes} -> {n_despues} registros "
                  f"({n_antes - n_despues} descartados)")
            return df
        else:
            print(f"    ADVERTENCIA: No hay columnas geográficas. Sin filtro.")
            return df

    df = df[df[columna].astype(str).str.strip() == str(cod_dpto)].copy()

    n_despues = len(df)
    print(f"    Filtro Tolima por {etiqueta}: "
          f"{n_antes} -> {n_despues} registros "
          f"({n_antes - n_despues} descartados)")
    return df


def convertir_fechas(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte columnas de fecha a datetime."""
    for col in COLUMNAS_FECHA:
        if col in df.columns:
            df[col] = pd.to_datetime(
                df[col], errors="coerce", format="mixed", dayfirst=True
            )
    return df


def convertir_numericos(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte columnas numéricas de string a tipos numéricos."""
    df = df.loc[:, ~df.columns.duplicated()]
    for col in COLUMNAS_NUMERICAS_INT:
        if col in df.columns:
            try:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            except Exception:
                pass
    return df


def eliminar_duplicados(df: pd.DataFrame) -> pd.DataFrame:
    """Elimina filas completamente duplicadas."""
    n_antes = len(df)
    df = df.drop_duplicates()
    n_despues = len(df)
    print(f"    Duplicados eliminados: {n_antes - n_despues}")
    return df


def transformar_datos(df_crudo: pd.DataFrame, nombre_tabla: str = "") -> pd.DataFrame:
    """
    Función principal de transformación para un único evento/archivo.
    Aplica secuencialmente todas las transformaciones.

    Args:
        df_crudo: DataFrame crudo de un archivo BD-*.xlsx.
        nombre_tabla: Nombre de la tabla (para mensajes de log).

    Returns:
        DataFrame limpio, anonimizado y filtrado, listo para carga.
    """
    etiqueta = f" [{nombre_tabla}]" if nombre_tabla else ""
    print(f"\n  TRANSFORMANDO{etiqueta}: "
          f"{df_crudo.shape[0]} filas x {df_crudo.shape[1]} columnas")

    # 0. Eliminar columnas duplicadas
    df = df_crudo.copy()
    n_dup = df.columns.duplicated().sum()
    if n_dup > 0:
        df = df.loc[:, ~df.columns.duplicated()]

    # 1. Normalizar nombres de columnas
    df = normalizar_columnas(df)

    # 2. Estandarizar valores nulos
    df = estandarizar_nulos(df)

    # 3. Anonimizar PII
    df = anonimizar_pii(df)

    # 4. Filtrar por Tolima
    df = filtrar_departamento(df)

    # Si no quedaron registros del Tolima, retornar DataFrame vacío
    if df.empty:
        print(f"    Sin registros del Tolima para{etiqueta}.")
        return df

    # 5. Convertir fechas
    df = convertir_fechas(df)

    # 6. Convertir numéricos
    df = convertir_numericos(df)

    # 7. Eliminar duplicados
    df = eliminar_duplicados(df)

    print(f"    Resultado{etiqueta}: {df.shape[0]} filas x {df.shape[1]} columnas")
    return df


def generar_reporte_global(lista_resultados: list, ruta_salida: str):
    """
    Genera un reporte de calidad consolidado y gráficas a partir de
    todos los DataFrames procesados.

    Args:
        lista_resultados: Lista de tuplas (df_limpio, nombre_tabla).
        ruta_salida: Carpeta donde guardar gráficas y reportes.
    """
    print("\n" + "=" * 60)
    print("REPORTE GLOBAL DE CALIDAD")
    print("=" * 60)

    # Consolidar para reporte (no para carga)
    dfs_validos = [df for df, _ in lista_resultados if not df.empty]
    if not dfs_validos:
        print("  No hay datos para el reporte.")
        return

    df_reporte = pd.concat(dfs_validos, ignore_index=True, sort=False)
    print(f"  Total consolidado para reporte: {df_reporte.shape[0]} filas")

    # Resumen por tabla
    print(f"\n  Resumen por tabla:")
    for df, nombre in lista_resultados:
        estado = f"{df.shape[0]} filas x {df.shape[1]} cols" if not df.empty else "SIN DATOS (0 registros Tolima)"
        print(f"    {nombre}: {estado}")

    # Gráficas
    os.makedirs(ruta_salida, exist_ok=True)
    try:
        fig, axes = plt.subplots(1, 2, figsize=(16, 7))

        # Top 15 eventos por frecuencia
        if "nom_eve" in df_reporte.columns:
            top = df_reporte["nom_eve"].value_counts().head(15)
            top.plot(kind="barh", ax=axes[0], color="#2196F3", edgecolor="black")
            axes[0].set_title("Top 15 Eventos por Frecuencia (Tolima)")
            axes[0].set_xlabel("Número de Registros")
            axes[0].set_ylabel("")
            axes[0].invert_yaxis()

        # Distribución por año
        if "año" in df_reporte.columns:
            years = df_reporte["año"].dropna().astype(int).value_counts().sort_index()
            years.plot(kind="bar", ax=axes[1], color="#4CAF50", edgecolor="black")
            axes[1].set_title("Registros por Año")
            axes[1].set_xlabel("Año")
            axes[1].set_ylabel("Número de Registros")
            axes[1].tick_params(axis="x", rotation=45)

        plt.tight_layout()
        ruta_grafica = os.path.join(ruta_salida, "distribucion_datos.png")
        plt.savefig(ruta_grafica, dpi=150)
        plt.close()
        print(f"\n  Gráfica guardada: {ruta_grafica}")
    except Exception as e:
        print(f"  ADVERTENCIA al generar gráfica: {e}")

    del df_reporte


if __name__ == "__main__":
    from extract import extraer_datos
    resultados = extraer_datos()
    for df, nombre_tabla, ruta in resultados[:3]:
        df_limpio = transformar_datos(df, nombre_tabla)
        print(f"  {nombre_tabla}: {df_limpio.shape}")
