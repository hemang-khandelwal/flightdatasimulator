import numpy as np 
from Database.AeroModel import AeroModel
from Database.Environment import ISA
from Mechanics.Forces import Forces
from Mechanics.Integrator import RK4
from Mechanics.Dynamics import AircraftDynamics
from Mechanics.Controls import Controls

controls = Controls()
isa = ISA(1)
plane = AeroModel(1,1,20)
forces = Forces(plane,122,123)
environment = ISA(1)
dynamics = AircraftDynamics(environment,plane,forces,controls)
rk4 = RK4(dynamics)
controls = Controls() 

# Space State Vector: [ u, w, q, theta, x, z ]
dt = 0.1

state = np.array([
    0,     # u     (m/s)
    0.0,      # w     (m/s)
    0.0,      # q     (rad/s)
    0,     # theta (rad)
    0.0,      # x     (m)
    30000  # z     (m)
])


totalTime = 10 # seconds 

noOfSteps = int(totalTime / dt)


for step in range(1, noOfSteps):
    t = dt*step
    state = rk4.timeStep(step, state, dt)
    print("Time:", t, "SSV:", state)






