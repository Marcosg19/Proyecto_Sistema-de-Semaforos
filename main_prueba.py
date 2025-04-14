import simpy
import random
import pandas as pd
import numpy as np
import scipy.stats as stats
import matplotlib.pyplot as plt

# Parámetros Globales
CALLES = ["Norte-L1", "Sur-L2", "Este-L3", "Oeste-L4"]

# Intervalo promedio de llegada de carros en cada calle (segundos)
INTERVALO_LLEGADA_CARROS = {
    "Norte-L1": 30,
    "Sur-L2": 30,
    "Este-L3": 7.5,
    "Oeste-L4": 7.5
}

# Intervalo promedio de llegada de peatones
INTERVALO_LLEGADA_PEATONES = 30

# Duración de simulación (1 hora)
TIEMPO_SIMULACION = 3600

# Tiempo de cruce de peatón
TIEMPO_PASO_PEATON = 6

# Tiempo entre cruce de autos
TIEMPO_ENTRE_CARROS = 1

# Cantidad de repeticiones por escenario
REPETS = 5

# Definición de escenarios (cada uno con tiempos de verde diferentes)
ESCENARIOS = [
    {"nombre": "Escenario_1", "Norte-L1": 30, "Sur-L2": 30, "Este-L3": 180, "Oeste-L4": 180},
    {"nombre": "Escenario_2", "Norte-L1": 25, "Sur-L2": 25, "Este-L3": 40, "Oeste-L4": 40},
    {"nombre": "Escenario_3", "Norte-L1": 25, "Sur-L2": 25, "Este-L3": 60, "Oeste-L4": 60},
    {"nombre": "Escenario_4", "Norte-L1": 30, "Sur-L2": 30, "Este-L3": 120, "Oeste-L4": 120}
]

# Clase que representa cada semáforo
class Semaforo:
    def __init__(self, env, nombre):
        self.env = env
        self.nombre = nombre
        self.cola = []  # Carros esperando
        self.pasados = 0  # Carros que lograron cruzar
        self.tiempos_espera = []  # Tiempo de espera de cada carro

    def agregar_carro(self, llegada):
        self.cola.append(llegada)

# Clase que representa toda la intersección
class Interseccion:
    def __init__(self, env, tiempos_verde):
        self.env = env
        self.tiempos_verde = tiempos_verde  # Tiempo verde de cada calle
        self.semaforos = {nombre: Semaforo(env, nombre) for nombre in CALLES}
        self.cola_peatones = []  # Lista de peatones esperando
        self.espera_peatones = []  # Tiempo de espera de peatones

        for calle in CALLES:
            self.env.process(self.generar_carros(calle))

        self.env.process(self.generar_peatones())
        self.env.process(self.controlar_semaforos())

    # Genera los carros en cada calle con base en su intervalo de llegada
    def generar_carros(self, calle):
        while True:
            yield self.env.timeout(random.expovariate(1.0 / INTERVALO_LLEGADA_CARROS[calle]))
            self.semaforos[calle].agregar_carro(self.env.now)

    # Genera peatones con base en su intervalo de llegada
    def generar_peatones(self):
        while True:
            yield self.env.timeout(random.expovariate(1.0 / INTERVALO_LLEGADA_PEATONES))
            self.cola_peatones.append(self.env.now)

    # Controla las fases de los semáforos y permite cruce de peatones
    def controlar_semaforos(self):
        while True:
            for calle in CALLES:
                inicio_fase = self.env.now
                ultimo_cruce = self.env.now  # Último carro que cruzó

                # Mientras el semáforo esté en verde
                while (self.env.now - inicio_fase) < self.tiempos_verde[calle]:
                    if self.semaforos[calle].cola:
                        llegada = self.semaforos[calle].cola.pop(0)
                        paso = random.uniform(2, 3)  # Tiempo aleatorio de cruce
                        # El carro empieza a cruzar según el momento correcto
                        inicio_cruce = max(self.env.now, llegada, ultimo_cruce + TIEMPO_ENTRE_CARROS)
                        yield self.env.timeout(max(0, inicio_cruce - self.env.now))
                        yield self.env.timeout(paso)
                        self.semaforos[calle].tiempos_espera.append(inicio_cruce - llegada)
                        self.semaforos[calle].pasados += 1
                        ultimo_cruce = inicio_cruce
                    else:
                        yield self.env.timeout(1)

                # Luego paso peatonal (todos los semáforos en rojo)
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


# Lista para almacenar todos los resultados
resultados = []

# Ejecución de todas las simulaciones por escenario y repeticiones
for escenario in ESCENARIOS:
    for rep in range(REPETS):
        env = simpy.Environment()
        interseccion = Interseccion(env, escenario)
        env.run(until=TIEMPO_SIMULACION)

        # Diccionario para guardar los resultados de esta repetición
        res = {
            "Escenario": escenario["nombre"],
            "Repeticion": rep+1,
            "Peatones_Pasados": len(interseccion.espera_peatones),
            "Peatones_Cola": len(interseccion.cola_peatones),
            "Espera_Prom_Pea": np.mean(interseccion.espera_peatones) if interseccion.espera_peatones else 0,
            "Tamaño_Cola_Pea": len(interseccion.cola_peatones)
        }

        # Guardar los resultados por cada calle individualmente
        for calle in CALLES:
            semaforo = interseccion.semaforos[calle]
            res[f"{calle}_Pasados"] = semaforo.pasados
            res[f"{calle}_Cola"] = len(semaforo.cola)
            res[f"{calle}_Espera_Prom"] = np.mean(semaforo.tiempos_espera) if semaforo.tiempos_espera else 0
            res[f"{calle}_Tam_Cola"] = len(semaforo.cola)

        resultados.append(res)

# Crear DataFrame con todos los resultados
df = pd.DataFrame(resultados)

# Guardar todos los resultados en .csv
df.to_csv("resultados.csv", index=False)

# Generar TXT por escenario
for escenario in ESCENARIOS:
    df_esc = df[df["Escenario"] == escenario["nombre"]]

    with open(f"Resultado_{escenario['nombre']}.txt", "w", encoding="utf-8") as f:
        f.write(f"RESULTADOS DEL {escenario['nombre']}\n\n")
        f.write(">>> Tiempos de Semáforo <<<\n")
        for calle in CALLES:
            f.write(f"{calle}: {escenario[calle]} segundos\n")
        f.write("\n")

        # Resultados por cada repetición
        for idx, row in df_esc.iterrows():
            f.write(f"Repetición {int(row['Repeticion'])}:\n\n")

            f.write(">>> Vehículos <<<\n")
            for calle in CALLES:
                f.write(f"{calle} -> Pasaron: {int(row[f'{calle}_Pasados'])} | En espera: {int(row[f'{calle}_Cola'])}\n")
                f.write(f"Tiempo Promedio de Espera: {round(row[f'{calle}_Espera_Prom'], 2)} seg\n")

            f.write("\n>>> Peatones <<<\n")
            f.write(f"Cruzaron: {int(row['Peatones_Pasados'])}\n")
            f.write(f"En espera: {int(row['Peatones_Cola'])}\n")
            f.write(f"Tiempo Promedio Espera Peatones: {round(row['Espera_Prom_Pea'], 2)} seg\n")
            f.write("\n-------------------------------------\n\n")

        # Resumen general del escenario (promedio de las 5 repeticiones)
        resumen = df_esc.mean(numeric_only=True)

        f.write("===== RESUMEN GENERAL DEL ESCENARIO =====\n\n")

        for calle in CALLES:
            f.write(f"{calle}:\n")
            f.write(f"Promedio Tiempo Espera Vehículos: {round(resumen[f'{calle}_Espera_Prom'], 2)} seg\n")
            f.write(f"Tamaño Promedio Cola Vehículos: {round(resumen[f'{calle}_Tam_Cola'], 2)}\n\n")

        f.write(">>> Peatones <<<\n")
        f.write(f"Promedio Tiempo Espera Peatones: {round(resumen['Espera_Prom_Pea'], 2)} seg\n")
        f.write(f"Tamaño Promedio Cola Peatones: {round(resumen['Tamaño_Cola_Pea'], 2)}\n")

print("Simulación completada correctamente y archivos TXT generados.")

# Crear gráficas de tiempos de espera por cada calle y escenario
for escenario in ESCENARIOS:
    df_esc = df[df["Escenario"] == escenario["nombre"]]

    plt.figure(figsize=(10, 6))

    # Graficar tiempo promedio de espera por calle
    for calle in CALLES:
        plt.plot(df_esc["Repeticion"], df_esc[f"{calle}_Espera_Prom"], label=f"{calle}")

    plt.xlabel("Repetición")
    plt.ylabel("Tiempo Promedio de Espera (segundos)")
    plt.title(f"Tiempos de Espera Promedio por Fase - {escenario['nombre']}")
    plt.legend()
    plt.grid(True)
    plt.ylim(0,1000)
    plt.xticks([1, 2, 3, 4, 5])
    plt.tight_layout()
    plt.savefig(f"Grafica_TiemposEspera_{escenario['nombre']}.png")
    plt.close()

# Crear histograma comparativo entre escenarios (tiempos espera vehiculos promedio global)
plt.figure(figsize=(10, 6))

promedios = []
nombres_escenarios = []

# Calcular promedio global de todos los tiempos de espera de vehículos en cada escenario
for escenario in ESCENARIOS:
    df_esc = df[df["Escenario"] == escenario["nombre"]]
    prom_total = df_esc[[f"{c}_Espera_Prom" for c in CALLES]].mean(axis=1).mean()
    promedios.append(prom_total)
    nombres_escenarios.append(escenario["nombre"])

plt.bar(nombres_escenarios, promedios, color='skyblue')
plt.xlabel("Escenario")
plt.ylabel("Tiempo Promedio de Espera Vehículos (segundos)")
plt.title("Comparación Tiempos Promedio de Espera Vehículos entre Escenarios")
plt.tight_layout()
plt.savefig("Histograma_Comparacion_TiemposEspera_Vehiculos.png")
plt.close()

print("Gráficas generadas y guardadas exitosamente.")