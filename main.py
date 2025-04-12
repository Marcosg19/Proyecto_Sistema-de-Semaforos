import simpy
import random
import pandas as pd
import numpy as np
import scipy.stats as stats
import matplotlib.pyplot as plt

# Parámetros globales de la simulación
CALLES = ["Norte-L1", "Sur-L2", "Este-L3", "Oeste-L4"]

# Intervalo de llegada promedio de los carros por calle (segundos)
INTERVALO_LLEGADA_CARROS = {
    "Norte-L1": 20, "Sur-L2": 20,
    "Este-L3": 7.5, "Oeste-L4": 7.5
}

INTERVALO_LLEGADA_PEATONES = 30  # Intervalo de llegada promedio de peatones
TIEMPO_SIMULACION = 1800  # Duración de cada simulación en segundos
TIEMPO_PASO_PEATON = 6  # Tiempo necesario para que crucen los peatones
TIEMPO_ENTRE_CARROS = 1  # Tiempo mínimo entre carros cruzando
REPETS = 5  # Número de repeticiones por escenario

# Definición de los escenarios a evaluar
ESCENARIOS = [
    {"nombre": "Escenario_1", "Norte-L1": 30, "Sur-L2": 30, "Este-L3": 180, "Oeste-L4": 180},
    {"nombre": "Escenario_2", "Norte-L1": 25, "Sur-L2": 25, "Este-L3": 40, "Oeste-L4": 40},
    {"nombre": "Escenario_3", "Norte-L1": 30, "Sur-L2": 30, "Este-L3": 60, "Oeste-L4": 60},
    {"nombre": "Escenario_4", "Norte-L1": 30, "Sur-L2": 30, "Este-L3": 120, "Oeste-L4": 120}
]

# Clase para manejar los semáforos
class Semaforo:
    def __init__(self, env, nombre):
        self.env = env # Entorno de simulación
        self.nombre = nombre # Nombre del semáforo
        self.cola = [] # Cola de carros esperando
        self.pasados = 0 # Contador de carros que han pasado
        self.tiempos_espera = [] # Lista de tiempos de espera de los carros

    def agregar_carro(self, llegada):
        self.cola.append(llegada)

# Clase para manejar toda la intersección
class Interseccion:
    def __init__(self, env, tiempos_verde):
        self.env = env
        self.tiempos_verde = tiempos_verde # Tiempos verdes de cada calle
        self.semaforos = {nombre: Semaforo(env, nombre) for nombre in CALLES}
        self.cola_peatones = []
        self.espera_peatones = []

        # Generación de carros y peatones
        for calle in CALLES:
            self.env.process(self.generar_carros(calle))
        self.env.process(self.generar_peatones())
        self.env.process(self.controlar_semaforos())

    def generar_carros(self, calle):
        # Genera la llegada de carros según un proceso exponencial
        while True:
            yield self.env.timeout(random.expovariate(1.0 / INTERVALO_LLEGADA_CARROS[calle]))
            self.semaforos[calle].agregar_carro(self.env.now)

    def generar_peatones(self):
        # Genera la llegada de peatones
        while True:
            yield self.env.timeout(random.expovariate(1.0 / INTERVALO_LLEGADA_PEATONES))
            self.cola_peatones.append(self.env.now)

    def controlar_semaforos(self):
        # Controla el funcionamiento de los semáforos y los cruces
        while True:
            for calle in CALLES:
                inicio_fase = self.env.now
                ultimo_cruce = self.env.now

                # Cruce de vehículos mientras esté verde
                while (self.env.now - inicio_fase) < self.tiempos_verde[calle]:
                    if self.semaforos[calle].cola:
                        llegada = self.semaforos[calle].cola.pop(0)
                        paso = random.uniform(2, 3)
                        inicio_cruce = max(self.env.now, llegada, ultimo_cruce + TIEMPO_ENTRE_CARROS)
                        yield self.env.timeout(max(0, inicio_cruce - self.env.now))
                        yield self.env.timeout(paso)
                        self.semaforos[calle].tiempos_espera.append(inicio_cruce - llegada)
                        self.semaforos[calle].pasados += 1
                        ultimo_cruce = inicio_cruce
                    else:
                        yield self.env.timeout(1)

                # Cruce de peatones cuando todos los semáforos están en rojo
                tiempo_disponible = 20
                while tiempo_disponible >= TIEMPO_PASO_PEATON:
                    if not self.cola_peatones:
                        yield self.env.timeout(1)
                        tiempo_disponible -= 1
                    else:
                        llegada = self.cola_peatones.pop(0)
                        espera = self.env.now - llegada
                        self.espera_peatones.append(espera)
                        yield self.env.timeout(TIEMPO_PASO_PEATON)
                        tiempo_disponible -= TIEMPO_PASO_PEATON

# --------------------- Simulación principal --------------------------

resultados = []

for escenario in ESCENARIOS:
    for rep in range(REPETS):
        env = simpy.Environment()
        interseccion = Interseccion(env, escenario)
        env.run(until=TIEMPO_SIMULACION)

        res = {
            "Escenario": escenario["nombre"],
            "Repeticion": rep+1,
            "Peatones_Pasados": len(interseccion.espera_peatones),
            "Peatones_Cola": len(interseccion.cola_peatones),
            "Espera_Prom_Veh": np.mean([np.mean(s.tiempos_espera) if s.tiempos_espera else 0 for s in interseccion.semaforos.values()]),
            "Espera_Prom_Pea": np.mean(interseccion.espera_peatones) if interseccion.espera_peatones else 0,
            "Tamaño_Cola_Veh": np.mean([len(s.cola) for s in interseccion.semaforos.values()]),
            "Tamaño_Cola_Pea": len(interseccion.cola_peatones),
        }

        for calle in CALLES:
            res[f"{calle}_Pasados"] = interseccion.semaforos[calle].pasados
            res[f"{calle}_Cola"] = len(interseccion.semaforos[calle].cola)

        resultados.append(res)

df = pd.DataFrame(resultados)
# Guardado de resultados
df.to_csv("resultados.csv", index=False)
df.groupby("Escenario").mean(numeric_only=True).reset_index().to_csv("resultados.csv", index=False)

# Crear .txt ordenados
for escenario in ESCENARIOS:
    df_esc = df[df["Escenario"] == escenario["nombre"]]
    resumen = df_esc.mean(numeric_only=True)
#    desviacion = df_esc.std(numeric_only=True)
#    t_val = stats.t.ppf(1-0.025, df=len(df_esc)-1)
#    margen_error = desviacion/np.sqrt(len(df_esc))*t_val
        
    with open(f"Resultado_{escenario['nombre']}.txt", "w", encoding="utf-8") as f:
        f.write(f"RESULTADOS DEL {escenario['nombre']}\n\n")
        f.write(">>> Tiempos de semáforo <<<\n")
        for calle in CALLES:
            f.write(f"{calle}: {escenario[calle]} segundos\n")
        
        f.write("\n")
        for _, row in df_esc.iterrows():
            f.write(f"Repetición {int(row['Repeticion'])}:\n\n")

            f.write(">>> Vehículos <<<\n")
            for calle in CALLES:
                f.write(f"{calle} → Pasaron: {int(row[f'{calle}_Pasados'])} | En espera: {int(row[f'{calle}_Cola'])}\n")

            f.write("\n>>> Peatones <<<\n")
            f.write(f"Cruzaron: {int(row['Peatones_Pasados'])}\n")
            f.write(f"En espera: {int(row['Peatones_Cola'])}\n\n")

            f.write("---- Métricas ----\n")
            f.write(f"Tiempo espera Vehículos: {round(row['Espera_Prom_Veh'],2)} seg\n")
            f.write(f"Tiempo espera Peatones: {round(row['Espera_Prom_Pea'],2)} seg\n")
            for calle in CALLES:
                f.write(f"Tamaño promedio de cola en {calle}: {round(df_esc[f"{calle}_Cola"].mean(),2)}\n")
                
            #f.write(f"Tamaño promedio cola Vehículos: {round(row['Tamaño_Cola_Veh'],2)}\n")
            f.write(f"Tamaño promedio cola Peatones: {round(row['Tamaño_Cola_Pea'],2)}\n\n")

        # Agregar Resumen General de las 5 repeticiones
        f.write("===== RESUMEN GENERAL DEL ESCENARIO =====\n\n")
        f.write(f"Promedio Tiempo espera Vehículos: {round(df_esc['Espera_Prom_Veh'].mean(), 2)} seg\n")
        f.write(f"Promedio Tiempo espera Peatones: {round(df_esc['Espera_Prom_Pea'].mean(), 2)} seg\n")
        f.write(f"Promedio Tamaño cola Vehículos: {round(df_esc['Tamaño_Cola_Veh'].mean(), 2)}\n")
        f.write(f"Promedio Tamaño cola Peatones: {round(df_esc['Tamaño_Cola_Pea'].mean(), 2)}\n")

    # Archivo escalar (.sca) → Promedio de las 5 repeticiones
    with open(f"{escenario['nombre']}.sca", "w", encoding="utf-8") as f:
        f.write(f"scalar {escenario['nombre']} TiempoEsperaVehiculos {round(df_esc['Espera_Prom_Veh'].mean(), 4)}\n")
        f.write(f"scalar {escenario['nombre']} TiempoEsperaPeatones {round(df_esc['Espera_Prom_Pea'].mean(), 4)}\n")
        f.write(f"scalar {escenario['nombre']} TamanoColaVehiculos {round(df_esc['Tamaño_Cola_Veh'].mean(), 4)}\n")
        f.write(f"scalar {escenario['nombre']} TamanoColaPeatones {round(df_esc['Tamaño_Cola_Pea'].mean(), 4)}\n")

    # Archivo vectorial (.vec) → Resultado de cada repetición
    with open(f"{escenario['nombre']}.vec", "w", encoding="utf-8") as f:
        f.write(f'vector {escenario["nombre"]}_Vehiculos TiempoEsperaVehiculos\n')
        f.write(f'vector {escenario["nombre"]}_Peatones TiempoEsperaPeatones\n')
        for _, row in df_esc.iterrows():
            f.write(f"{int(row['Repeticion'])} {round(row['Espera_Prom_Veh'], 4)}\n")
        for _, row in df_esc.iterrows():
            f.write(f"{int(row['Repeticion'])} {round(row['Espera_Prom_Pea'], 4)}\n")


        plt.figure(figsize=(10, 6))

    for calle in CALLES:
        plt.plot(df_esc["Repeticion"], df_esc[f"{calle}_Cola"], marker='o', label=calle)

    plt.title(f"Tamaño promedio de cola por fase - {escenario['nombre']}")
    plt.xlabel("Repetición")
    plt.ylabel("Vehículos en cola (Promedio)")
    plt.legend()
    plt.grid(True)
    plt.savefig(f"Grafica_Tiempos_Espera_{escenario['nombre']}.png", dpi=300)
    plt.close()


    promedios_vehiculos = df.groupby("Escenario")["Espera_Prom_Veh"].mean()

    plt.figure(figsize=(8, 6))
    plt.bar(promedios_vehiculos.index, promedios_vehiculos.values, color='skyblue')
    plt.xlabel("Escenarios")
    plt.ylabel("Tiempo promedio de espera de vehículos (segundos)")
    plt.title("Comparación de tiempos de espera promedio de vehículos por escenario")
    plt.xticks(rotation=20)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.savefig("Histograma_Tiempos_Espera_Vehiculos.png", dpi=300)
    plt.close()

#        f.write("Resumen Promedio:\n\n")
#        for col in df_esc.columns[2:]:
#            f.write(f"{col}:\n")
#            f.write(f"  Media: {round(resumen[col],2)}\n")
#            f.write(f"  Desviación estándar: {round(desviacion[col],2)}\n")
#            f.write(f"  IC 95%: [{round(resumen[col]-margen_error[col],2)} - {round(resumen[col]+margen_error[col],2)}]\n\n")

print("Simulación completada. Archivos .vec, .sca y .txt generados correctamente.")