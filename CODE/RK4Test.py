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
dt = 0.001
#gamma_trim = np.atan2(0, 1000)
#theta_trim = (1.8221176122649494 *(np.pi)/180 ) + gamma_trim

V = 70          # m/s (C172 cruise-ish)
alpha = 0.05   # ~3 degrees
u = V*np.cos(alpha)
w = V*np.sin(alpha)

state = np.array([
    u,     # u     (m/s)
    w,      # w     (m/s)
    0.0,      # q     (rad/s)
    alpha,     # theta (rad)
    0,      # x     (m)
    3000  # z     (m)
])


totalTime = 2 # seconds 

noOfSteps = int(totalTime / dt)


for step in range(1, noOfSteps):
    t = dt*step
    state = rk4.timeStep(step, state, dt)
    print("Time:", t, "SSV:", state)






