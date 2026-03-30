
import matplotlib.pyplot as plt
#import seaborn as sns

def transformar_datos(df_estudiantes, df_academico):
    print("Transformando datos...")
    

    #Describir los datasets, caracterizar, tpos de datos, valor nules, cuantas filas, cuantas columnas

    print("Información básica del dataset de estudiantes:")
    print(df_estudiantes.info())
    print("\nInformación básica del dataset académico:")
    print(df_academico.info())  

    #analítica descriptiva (medias, medianas, moda, desviación estándar, etc)
    print("\nEstadísticas descriptivas del dataset de estudiantes:")
    print(df_estudiantes.describe())

    print("\nEstadísticas descriptivas del dataset académico:")
    print(df_academico.describe())

    #pre-visualizción para conocer la distribución de los datos, detectar outliers, etc

    plt.figure(figsize=(10, 6))
    plt.subplot(1, 2, 1)
    plt.hist(df_academico["historical_gpa"], bins=20, color='blue', edgecolor='black')
    plt.xlabel("Promedio Histórico")
    plt.ylabel("Frecuencia")
    plt.title("Distribución del Promedio Histórico")
    plt.grid(True)
    
    plt.subplot(1, 2, 2)
    plt.hist(df_academico["credits_completed"], bins=20, color='#39A0A3', edgecolor='black')
    plt.xlabel("Créditos Completados")
    plt.ylabel("Frecuencia")
    plt.title("Distribución de Créditos Completados")   
    plt.grid(True)
    plt.tight_layout()
    #plt.show()

    plt.savefig("data/processed/distribucion_datos.png")

    #detectar duplicados, nulosº
    print("\nNúmero de valores nulos en el dataset de estudiantes:")
    print(df_estudiantes.isnull().sum())
    print("\nNúmero de valores nulos en el dataset académico:")
    print(df_academico.isnull().sum())

    #duplicados
    print("\nNúmero de filas duplicadas en el dataset de estudiantes:")
    print(df_estudiantes.duplicated().sum())
    print("\nNúmero de filas duplicadas en el dataset académico:")
    print(df_academico.duplicated().sum())

    #eliminar duplicados
    df_estudiantes = df_estudiantes.drop_duplicates()
    df_academico = df_academico.drop_duplicates()

    print("\nNúmero de filas después de eliminar duplicados en el dataset de estudiantes:")
    print(df_estudiantes.shape[0])
    print("\nNúmero de filas después de eliminar duplicados en el dataset académico:")
    print(df_academico.shape[0])

    
    #normaizar nombres de columnas, eliminar espacios, poner todo en minúscula, reemplazar espacios por guiones bajos, etc. para facilitar el manejo de los datos y evitar problemas al momento de hacer joins o consultas a la base de datos.
    df_estudiantes.columns = df_estudiantes.columns.str.strip().str.lower().str.replace(" ", "_")
    df_academico.columns = df_academico.columns.str.strip().str.lower().str.replace(" ", "_")


   

  #imputar valores nulos, en este caso, vamos a imputar la media para la columna "historical_gpa" y la mediana para la columna "credits_completed", ya que son columnas numéricas y tienen una distribución sesgada.
    df_academico["historical_gpa"] = df_academico["historical_gpa"].fillna(df_academico["historical_gpa"].mean())
    df_academico["credits_completed"] = df_academico["credits_completed"].fillna(df_academico["credits_completed"].median())    


    

    datos_estudiantes_limpios = df_estudiantes.copy()   
    datos_academicos_limpios = df_academico.copy()


     # Join final
    df_final   = datos_estudiantes_limpios.merge(
    datos_academicos_limpios,
    on="student_id",
    how="left"
    )



    return df_final