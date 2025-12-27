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
stallMonitor = Stall(17,0.95,plane,environment,forces)
trimSolver = TrimSolver(0.005,0.005,1e-6,1000,plane, environment, forces, controls, stallMonitor)

solutions = trimSolver.multiStartTrimSolve(
    alpha0Array = [-5, -2, 0, 2, 5, 8, 12],
    e0Array = [-15, -10, -5, 0, 5, 10, 15],
    tolerance=2,
    u=1000,
    w=0,
    z=30000,
    q=0.0
)
print(solutions)


for a in range(-5, 15):
    print(a, plane.aeroval(a, "cm"))
