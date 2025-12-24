import numpy as np

class RK4: 
    def __init__(self,dynamics):
        self.dynamics = dynamics 

    def timeStep(self, time, state, dt ):
        f = self.dynamics.stateDerivatives # Stores the derivaties of the SSV (State Space Vector)

        k1 = f(time,state) # Approx for value at the beginning of the interval 
        k2 = f(time+dt/2, state + dt*(k1/2)) # Gives approximation for the midpoint 
        k3 = f(time + dt/2, state + dt*(k2/2)) # A better approximation for the midpoint
        k4 = f(time + dt, state + dt*k3) # Approx for value at the end of the interval 
        return state + (dt/6) * (k1 + 2*k2 + 2*k3 + k4) # Final Result is the Weighted Average for the values 
    


    



    
