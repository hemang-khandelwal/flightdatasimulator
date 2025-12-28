import numpy as np 
from Database.AeroModel import AeroModel
from Database.Environment import ISA
from Mechanics.Forces import Forces
from Mechanics.Integrator import RK4
from Mechanics.Dynamics import AircraftDynamics
from Mechanics.Controls import Controls
from Mechanics.TrimSolver import TrimSolver
from Perfomance.StallMonitor import Stall

controls = Controls()
isa = ISA(1)
plane = AeroModel(1,1,20)
forces = Forces(plane,122,123)
environment = ISA(1)
dynamics = AircraftDynamics(environment,plane,forces,controls)
rk4 = RK4(dynamics)
controls = Controls() 
stallMonitor = Stall(np.deg2rad(17),0.95,plane,environment,forces)
trimSolver = TrimSolver(0.005,0.005,1e-6,10000,plane, environment, forces, controls, stallMonitor)

alpha0 = np.deg2rad(np.array([-5, -2, 0, 2, 5, 8, 12]))
e0 = np.deg2rad(np.array([-15, -10, -5, 0, 5, 10, 15]))

solutions = trimSolver.multiStartTrimSolve(
    alpha0Array = alpha0,
    e0Array = e0,
    tolerance=2,
    u=65,
    w=0,
    z=1000,
    q=0.0
)

aoa = trimSolver.newtonRapshon(
    alpha0= np.deg2rad(5),
    e0 = np.deg2rad(4),
    u=1212,
    w=0,
    z=30000,
    q=0.0
) # type: ignore
print(solutions)

print (aoa)
