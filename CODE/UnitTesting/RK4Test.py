import numpy as np 
from Database.BaseAeroModel import AeroModel
from Database.Environment import ISA
from Mechanics.Forces import Forces
from Mechanics.Integrator import RK4
from Mechanics.Dynamics import AircraftDynamics
from Mechanics.Controls import Controls


from Perfomance.BlendedAeroModel import BlendedAeroModel
from Perfomance.StallManager import Stall


#### 
baseModel = AeroModel(1,1,20)

plane = BlendedAeroModel(
    baseAeroModel=baseModel,
    blendWidth= np.deg2rad(4.0),
    decayConstant = 3.0

)
###


controls = Controls()
isa = ISA(1)


forces = Forces(plane,122,123)
environment = ISA(1)
dynamics = AircraftDynamics(environment,plane,forces,controls)
rk4 = RK4(dynamics)
controls = Controls() 

## Pass in RAW Model 
stallMonitor = Stall(np.deg2rad(17),0.95,baseModel,environment,forces)



print("Blend")
print(plane.aeroval(np.deg2rad(180),"cd"))

print("RAW")
print(baseModel.aeroval(np.deg2rad(180),"cd"))
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

totalTime = 0.001# seconds 

noOfSteps = int(totalTime / dt)


for step in range(1, noOfSteps):
    t = dt*step
    state = rk4.timeStep(step, state, dt)
    if stallMonitor.isStateStall(state) == True: 
        print("STALL")
        stalledFlag = True 
    print("Time:", t, "SSV:", state)






