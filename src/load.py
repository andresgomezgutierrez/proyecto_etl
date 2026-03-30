import pandas as pd
import mysql.connector

def map_dtype(serie):
    """Mapea tipos de pandas a MySQL"""
    if pd.api.types.is_datetime64_any_dtype(serie):
        return "DATETIME"
    elif pd.api.types.is_integer_dtype(serie):
        return "INT"
    elif pd.api.types.is_float_dtype(serie):
        return "FLOAT"
    else:
        return "VARCHAR(255)"

def carga_datos(df_final, table_name="tabla_etl"):
    print("Iniciando carga de datos...")

    # Guardar respaldo CSV opcional
    df_final.to_csv("data/processed/datos_finales.csv", index=False)

    # Convertir nulos de pandas a None para MySQL
    df_insert = df_final.copy().astype(object)
    df_insert = df_insert.where(pd.notnull(df_insert), None)

    # Conexión
    conn = mysql.connector.connect(
        host="132.148.182.196",
        user="useruao",
        password="Autonoma20252",
        database="datosclientes"
    )

    cursor = conn.cursor()

    try:
        # 1. Crear tabla si no existe
        definiciones = []
        for col in df_final.columns:
            tipo_mysql = map_dtype(df_final[col])
            definiciones.append(f"`{col}` {tipo_mysql}")

        create_table_query = f"""
        CREATE TABLE IF NOT EXISTS `{table_name}` (
            id INT AUTO_INCREMENT PRIMARY KEY,
            {", ".join(definiciones)}
        )
        """
        cursor.execute(create_table_query)
        print(f"Tabla `{table_name}` creada o verificada correctamente.")

        # 2. Insertar datos
        columnas_sql = ", ".join([f"`{col}`" for col in df_insert.columns])
        placeholders = ", ".join(["%s"] * len(df_insert.columns))

        insert_query = f"""
        INSERT INTO `{table_name}` ({columnas_sql})
        VALUES ({placeholders})
        """

        data = [
            tuple(None if pd.isna(valor) else valor for valor in fila)
            for fila in df_insert.itertuples(index=False, name=None)
        ]

        cursor.executemany(insert_query, data)
        conn.commit()

        print(f"Se insertaron {cursor.rowcount} registros correctamente en `{table_name}`.")

    except Exception as e:
        conn.rollback()
        print(f"Error en la carga: {e}")
        raise

    finally:
        cursor.close()
        conn.close()
        print("Conexión cerrada.")