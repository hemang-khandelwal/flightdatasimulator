import numpy as np 
from Database.AeroModel import AeroModel
from Database.Environment import ISA
from Mechanics.Forces import Forces
from Mechanics.Integrator import RK4
from Mechanics.Dynamics import AircraftDynamics

isa = ISA(1)
plane = AeroModel(1,1,20)
forces = Forces(plane,122,123)
environment = ISA(1)
dynamics = AircraftDynamics(environment,plane,forces)
rk4 = RK4(dynamics)

# Space State Vector: [ u, w, q, theta, x, z ]
controls = 1
dt = 0.1

state = np.array([
    50.0,     # u     (m/s)
    0.0,      # w     (m/s)
    0.0,      # q     (rad/s)
    0.05,     # theta (rad)
    0.0,      # x     (m)
    1000.0    # z     (m)
])


totalTime = 300 # seconds 

noOfSteps = int(totalTime / dt)


for step in range(1, noOfSteps):
    t = dt*step
    state = rk4.timeStep(step, state, dt, controls)
    print("Time:", t, "SSV:", state)






