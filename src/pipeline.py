"""
Pipeline ETL - Vigilancia Epidemiológica SIVIGILA (Tolima)
==========================================================
Orquestador principal que ejecuta secuencialmente las tres fases
del proceso ETL, procesando CADA ARCHIVO en su propia tabla MySQL:

  1. EXTRACCIÓN:      Escaneo dinámico y lectura de archivos BD-*.xlsx
  2. TRANSFORMACIÓN:   Limpieza, anonimización, filtrado por archivo
  3. CARGA:           Full reload a MySQL (una tabla por evento) + CSV

Estrategia de carga: FULL RELOAD (DROP + CREATE + INSERT) por tabla.
Justificación: Los epidemiólogos pueden modificar registros históricos
al realizar unidades de análisis (ej. actualización de causa de muerte
en casos de tuberculosis). No existen variables de control de edición
en SIVIGILA, por lo que cada ejecución borra y recarga toda la información.

Autor: Wilson Andrés Gómez Gutiérrez
Proyecto: Sistema de Analítica Predictiva para Vigilancia Epidemiológica
          mediante Integración de Datos SIVIGILA y DANE - Caso Tolima
Asignatura: ETL - Maestría en IA y Ciencia de Datos
"""

import os
import gc
import time
from extract import extraer_datos
from transform import transformar_datos, generar_reporte_global
from load import carga_datos


def main():
    """
    Función principal del pipeline ETL.
    Procesa cada archivo BD-*.xlsx individualmente:
      Extraer → Transformar → acumular → Cargar todas las tablas.
    """
    print("*" * 60)
    print("  PIPELINE ETL - SIVIGILA TOLIMA")
    print("  Sistema de Vigilancia en Salud Pública")
    print("  Estrategia: FULL RELOAD (una tabla por evento)")
    print("*" * 60)

    inicio = time.time()

    # ─── FASE 1: EXTRACCIÓN ────────────────────────────────────────
    # Retorna lista de (DataFrame, nombre_tabla, ruta_archivo)
    archivos_extraidos = extraer_datos()

    # ─── FASE 2: TRANSFORMACIÓN (archivo por archivo) ──────────────
    print("\n" + "=" * 60)
    print("FASE 2: TRANSFORMACIÓN DE DATOS (por evento)")
    print("=" * 60)

    # Transformar cada archivo individualmente
    import pandas as pd
    transformados_por_tabla = {}  # {nombre_tabla: [df1, df2, ...]}

    for df_crudo, nombre_tabla, ruta_archivo in archivos_extraidos:
        df_limpio = transformar_datos(df_crudo, nombre_tabla)

        if not df_limpio.empty:
            if nombre_tabla not in transformados_por_tabla:
                transformados_por_tabla[nombre_tabla] = []
            transformados_por_tabla[nombre_tabla].append(df_limpio)

        # Liberar memoria del DataFrame crudo
        del df_crudo
        gc.collect()

    # Fusionar archivos que mapean a la misma tabla
    # (ej. dos BD-813.xlsx de TB en carpetas distintas van a evento_813)
    lista_transformados = []
    for nombre_tabla, dfs in transformados_por_tabla.items():
        if len(dfs) > 1:
            df_merged = pd.concat(dfs, ignore_index=True, sort=False)
            df_merged = df_merged.drop_duplicates()
            print(f"  [MERGE] {nombre_tabla}: {len(dfs)} archivos "
                  f"-> {df_merged.shape[0]} filas combinadas")
            lista_transformados.append((df_merged, nombre_tabla))
        else:
            lista_transformados.append((dfs[0], nombre_tabla))

    del transformados_por_tabla
    gc.collect()

    # Generar reporte global con gráficas
    ruta_procesados = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "data", "processed"
    )
    generar_reporte_global(lista_transformados, ruta_procesados)

    # ─── FASE 3: CARGA ────────────────────────────────────────────
    carga_datos(lista_transformados)

    # ─── RESUMEN FINAL ─────────────────────────────────────────────
    fin = time.time()
    duracion = fin - inicio

    tablas_con_datos = sum(1 for df, _ in lista_transformados if not df.empty)
    total_registros = sum(df.shape[0] for df, _ in lista_transformados if not df.empty)

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETADO EXITOSAMENTE")
    print("=" * 60)
    print(f"  Archivos procesados:  {len(archivos_extraidos)}")
    print(f"  Tablas con datos:     {tablas_con_datos}")
    print(f"  Total registros:      {total_registros}")
    print(f"  Tiempo total:         {duracion:.2f} segundos")
    print("=" * 60)


if __name__ == "__main__":
    main()
