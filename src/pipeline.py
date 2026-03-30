#importar los modulos de extracción, transformación y carga
from extract import extraer_datos
from transform import transformar_datos
from load import carga_datos





def main():
    df_estudiantes, df_academico = extraer_datos()
    #print(df_estudiantes.head())
    # print(df_academico.head())

    df_final = transformar_datos(df_estudiantes, df_academico)
    print(df_final.head())

    carga_datos(df_final) #enviar datos a la base de datos, en este caso se guardan en un archivo csv



if __name__ == "__main__": #buena practica para evitar que el código se ejecute al importar el módulo
    main()


