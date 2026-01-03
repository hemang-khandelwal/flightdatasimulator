import numpy as np
import numpy as np 
from Database.BaseAeroModel import AeroModel
from Database.Environment import ISA
from Mechanics.Forces import Forces
from Mechanics.Integrator import RK4
from Mechanics.Dynamics import AircraftDynamics
from Mechanics.Controls import Controls
from Mechanics.TrimSolver import TrimSolver
from CODE.Perfomance.StallManager import Stall
from Sensors.Sensors import AttitudeSensor, Altimeter, PitotTube, Accelerometer, SensorManager




controls = Controls()
isa = ISA(1)
plane = AeroModel(1,1,20)
forces = Forces(plane,122,123)
environment = ISA(1)
dynamics = AircraftDynamics(environment,plane,forces,controls)
rk4 = RK4(dynamics)
controls = Controls() 
stallMonitor = Stall(np.deg2rad(17),0.95,plane,environment,forces)
trimSolver = TrimSolver(0.0005,0.005,1e-6,10000,plane, environment, forces, controls, stallMonitor)



# -----------------------------
# Fixed TRUE inputs (constant)
# -----------------------------

trueState = np.array([
    50.0,    # u
    -2.0,    # w
    0.05,    # q
    0.10,    # theta
    0.0,     # x
    1000.0   # z
])

stateDerivative = np.array([
    -0.5,    # u_dot
    -9.81,   # w_dot
    0.01,
    0.05,
    50.0,
    -2.0
])

dt = 0.01  # 100 Hz

# -----------------------------
# Instantiate sensors
# -----------------------------

manager = SensorManager()
manager.addSensor("attitude", AttitudeSensor(0.01, 50, True, "GAUSSIAN"))
manager.addSensor("altimeter", Altimeter(1.0, 10, True, "GAUSSIAN"))
manager.addSensor("airspeed", PitotTube(0.5, 20, True, "GAUSSIAN"))
manager.addSensor("vertical_accel", Accelerometer(0.2, 100, True, "GAUSSIAN"))

# -----------------------------
# True reference values
# -----------------------------

trueValues = {
    "attitude": trueState[3],
    "altimeter": trueState[5],
    "airspeed": np.sqrt(trueState[0]**2 + trueState[1]**2),
    "vertical_accel": stateDerivative[1]
}

# -----------------------------
# Test loop
# -----------------------------

print("=== SENSOR TEST START ===")

for step in range(50):
    measurements = manager.allSensorReadings(trueState, stateDerivative, dt)

    if step % 5 == 0:
        print(f"\nStep {step}")
        for name in measurements:
            print(
                f"{name:15s}: "
                f"true = {trueValues[name]:8.4f} | "
                f"measured = {measurements[name]:8.4f}"
            )

print("\n=== SENSOR TEST END ===")