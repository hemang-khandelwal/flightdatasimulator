import numpy as np 
from Database.AeroModel import AeroModel
from Database.Environment import ISA
from Mechanics.Forces import Forces
from Mechanics.Integrator import RK4
from Mechanics.Dynamics import AircraftDynamics
from Mechanics.Controls import Controls
from Mechanics.TrimSolver import TrimSolver

controls = Controls()
isa = ISA(1)
plane = AeroModel(1,1,20)
forces = Forces(plane,122,123)
environment = ISA(1)
dynamics = AircraftDynamics(environment,plane,forces,controls)
rk4 = RK4(dynamics)
controls = Controls() 
trimSolver = TrimSolver(0.005,0.005,1e-6,1000,plane, environment, forces, controls)

aoa, e = trimSolver.newtonRapshon(
    alpha0=10,     # ~3°
    e0=10.0,          # small elevator
    u=1,         # forward speed
    w=0,           # steady level
    z=10,        # altitude
    q=0.0
)
for a in range(-5, 15):
    print(a, plane.aeroval(a, "cm"))

print(aoa,e)


