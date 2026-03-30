
import pandas as pd

def extraer_datos():
    print("Extrayendo datos..")

    info_basica_estudiantes = pd.read_csv("data/raw/students_basic.csv") #data\\raw\\students_basic.csv
    info_academica_estudiantes = pd.read_csv("data/raw/students_historical_gp.csv") #data\\raw\\students_academic.csv

    
    


    return info_basica_estudiantes, info_academica_estudiantes