import simpy
import random

# Crear y abrir archivo para registrar los eventos de la simulación
log_file = open("eventos_simulacion.txt", "w")

# Función para escribir eventos en el archivo de log
def log_event(text):
    log_file.write(text + "\n")

# Definición de tiempos de semáforo verde por calle (en segundos)
TIEMPOS_VERDE = {
    "Norte-L1": 30,
    "Sur-L2": 30,
    "Este-L3": 60,
    "Oeste-L4": 60
}

# Tiempo que dura el paso peatonal
TIEMPO_PEATONAL = 20

# Intervalos promedio de llegada de vehículos por calle (segundos entre llegadas)
INTERVALO_LLEGADA_CARROS = {
    "Norte-L1": 20,
    "Sur-L2": 20,
    "Este-L3": 7.5,
    "Oeste-L4": 7.5
}
INTERVALO_LLEGADA_PEATONES = 30 # Intervalo promedio de llegada de peatones (segundos)
TIEMPO_SIMULACION = 1000 # Tiempo total de simulación (en segundos)
TIEMPO_PASO_PEATON = 6 # Tiempo que tarda un peatón en cruzar
TIEMPO_ENTRE_CARROS = 1  # Tiempo mínimo de separación entre carros cuando cruzan

# Lista de las calles que forman parte de la intersección
CALLES = ["Norte-L1", "Sur-L2", "Este-L3", "Oeste-L4"]

# Clase que representa cada semáforo de la intersección
class Semaforo:
    def __init__(self, env, nombre):
        self.env = env # Entorno de simulación
        self.nombre = nombre # Nombre de la calle del semáforo
        self.cola = [] # Lista de vehículos esperando
        self.pasados = 0 # Contador de vehículos que lograron cruzar

    # Método para agregar un carro a la cola
    def agregar_carro(self, carro):
        self.cola.append(carro)

# Clase que representa toda la intersección y su comportamiento
class Interseccion:
    def __init__(self, env):
        self.env = env
        # Crear un semáforo por cada calle
        self.semaforos = {nombre: Semaforo(env, nombre) for nombre in CALLES}
        self.cola_peatones = [] # Lista de peatones esperando
        self.pasaron_peatones = 0 # Contador de peatones que lograron cruzar

        # Crear procesos de generación de carros y peatones
        for calle in CALLES:
            self.env.process(self.generar_carros(calle))
        self.env.process(self.generar_peatones())
        self.env.process(self.controlar_semaforos()) # Control de fases

    # Generador de llegada de vehículos por calle
    def generar_carros(self, calle):
        while True:
            # Esperar un tiempo aleatorio antes de que llegue otro carro
            yield self.env.timeout(random.expovariate(1.0 / INTERVALO_LLEGADA_CARROS[calle]))
            # Agregar el carro al semáforo correspondiente
            self.semaforos[calle].agregar_carro(self.env.now)
            log_event(f"{self.env.now}: Llega un vehículo a {calle} - Vehículos en cola: {len(self.semaforos[calle].cola)}")
            tiempo_llega_carro=self.env.now
    
    # Generador de llegada de peatones
    def generar_peatones(self):
        while True:
            yield self.env.timeout(random.expovariate(1.0 / INTERVALO_LLEGADA_PEATONES))
            self.cola_peatones.append(self.env.now)
            log_event(f"{self.env.now}: Llega un peatón - Peatones esperando: {len(self.cola_peatones)}")

    # Controlador de las fases del semáforo
    def controlar_semaforos(self):
        while True:
            # Secuencia de semáforos
            for calle in CALLES:
                log_event(f"\n{self.env.now}: Semáforo VERDE en {calle}")
                carros_iniciales = len(self.semaforos[calle].cola)

                tiempo_verde = TIEMPOS_VERDE[calle] # Tiempo que estará en verde
                tiempo_inicio = self.env.now
                carros_que_pasan = 0

                ultimo_tiempo_cruce = self.env.now #inicializando cuando se pone en verde

                # Mientras el semáforo esté en verde
                while (self.env.now - tiempo_inicio) < tiempo_verde:
                    if self.semaforos[calle].cola:
                        tiempo_llega_carro = self.semaforos[calle].cola.pop(0)
                        carros_que_pasan += 1
                        tiempo_paso = random.uniform(2, 3) # Tiempo aleatorio que tarda en cruzar

                        # Calcular el momento en que puede empezar a cruzar
                        # El carro empieza a cruzar en cuanto llega o después de separacion
                        tiempo_inicio_cruce = max(self.env.now, tiempo_llega_carro, ultimo_tiempo_cruce + TIEMPO_ENTRE_CARROS)
                        yield self.env.timeout(tiempo_inicio_cruce - self.env.now)
                        yield self.env.timeout(tiempo_paso)

                        log_event(f"{tiempo_inicio_cruce+tiempo_paso}: Vehículo en {calle} - Llegó en: {tiempo_llega_carro} - Tiempo de cruce: {round(tiempo_paso,2)} segundos - Termina en: {round(tiempo_inicio_cruce + tiempo_paso,2)} - Vehículos restantes en cola: {len(self.semaforos[calle].cola)}")

                        ultimo_tiempo_cruce = tiempo_inicio_cruce  # Actualizo el último cruce
                    else:
                        yield self.env.timeout(1)


                self.semaforos[calle].pasados += carros_que_pasan

                carros_restantes = len(self.semaforos[calle].cola)
                log_event(f"{self.env.now}: Semáforo ROJO en {calle}")
                log_event(f"Resumen {calle} -> Carros que pasaron: {carros_que_pasan}, Carros en cola: {carros_restantes}")

            # Paso peatonal
            log_event(f"\n{self.env.now}: Paso peatonal activado - Todos en ROJO")
            peatones_que_pasan = 0
            tiempo_disponible = TIEMPO_PEATONAL

            while tiempo_disponible >= TIEMPO_PASO_PEATON:
                # Contar cuántos peatones estaban esperando antes del cruce
                peatones_listos = len(self.cola_peatones)

                if peatones_listos == 0:
                    yield self.env.timeout(1)
                    tiempo_disponible -= 1
                else:
                    # Cruzan todos los peatones que ya estaban en espera
                    peatones_que_pasan += peatones_listos
                    self.pasaron_peatones += peatones_listos
                    self.cola_peatones.clear()

                    yield self.env.timeout(TIEMPO_PASO_PEATON)
                    tiempo_disponible -= TIEMPO_PASO_PEATON

            log_event(f"{self.env.now}: Peatones que pasaron: {peatones_que_pasan}, Peatones que quedaron: {len(self.cola_peatones)}")
            yield self.env.timeout(1)

# Crear entorno de simulación
env = simpy.Environment()
interseccion = Interseccion(env)

# Ejecutar simulación
env.run(until=TIEMPO_SIMULACION)

# Reporte Final
log_event("\n===== RESULTADOS FINALES DE LA SIMULACIÓN =====\n")

log_event(">>> Vehículos <<<")
for nombre, semaforo in interseccion.semaforos.items():
    log_event(f"{nombre}:")
    log_event(f"  Total de vehículos que pasaron: {semaforo.pasados}")
    log_event(f"  Vehículos que quedaron en espera: {len(semaforo.cola)}")

log_event("\n>>> Peatones <<<")
log_event(f"Total de peatones que lograron cruzar: {interseccion.pasaron_peatones}")
log_event(f"Total de peatones que quedaron esperando: {len(interseccion.cola_peatones)}")

log_event("\n===== FIN DE LOS RESULTADOS =====")

print("\n===== RESULTADOS FINALES DE LA SIMULACIÓN =====\n")

print(">>> Vehículos <<<")
for nombre, semaforo in interseccion.semaforos.items():
    print(f"{nombre}:")
    print(f"  Total de vehículos que pasaron: {semaforo.pasados}")
    print(f"  Vehículos que quedaron en espera: {len(semaforo.cola)}")

print("\n>>> Peatones <<<")
print(f"Total de peatones que lograron cruzar: {interseccion.pasaron_peatones}")
print(f"Total de peatones que quedaron esperando: {len(interseccion.cola_peatones)}")

print("\n===== FIN DE LOS RESULTADOS =====")

log_file.close()