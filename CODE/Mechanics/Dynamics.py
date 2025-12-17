import numpy as np 
# Space State Vector: [ u, w, q, theta, x, z ]

class AircraftDynamics:
    def __init__(self, environment, aeroModel, forces): # Pass in Aircraft Module in later 
        # Passing the objects into the class 
        #self.aircraft = aircraft 
        self.environment = environment
        self.aeroModel = aeroModel
        self.forces = forces 

        self.stateVector = []


    def stateDerivatives(self,t, state, controls): 
        # Unpacking the SSV (State Space Vector)
        u, w, q, theta, x, z = state 
        # Theta = pitch 

        resultantV = np.sqrt(u**2 + w**2)
        gamma = np.arctan2(w,u) # Gamma = Flight Path Angle 

        aoa = theta - gamma

        cl = self.aeroModel.aeroval(aoa,"cl")
        cd = self.aeroModel.aeroval(aoa,"cd")
        cm = self.aeroModel.aeroval(aoa,"cm")

        L,D,M = self.forces.aeroForces(
            self.environment.density(z), # The vertical height(Z) is the elevation 
            resultantV,
            aoa
        )

        #T = controls.thrust 
        T = 1

        ## Resolving Forces 
        horiz = (self.forces.resolveForce(aoa,L,"sin")) -(self.forces.resolveForce(aoa,D,"cos")) + T 
        vert = -(self.forces.resolveForce(aoa,D,"sin")) -(self.forces.resolveForce(aoa,L,"cos"))  

        m = 12323
        Iy = 212
        g = 9.81

        theta_dot = q

        ## Equations of Motion 
        ## ACCELERATION
        u_dot = (horiz / m) - g*np.sin(theta) + w*q
        w_dot = (vert / m) + g*np.cos(theta) - u*q
        q_dot = M / Iy

        ## Kinematic Definitions 
        # Velocity 
        x_dot = u*np.cos(theta) - w*np.sin(theta)
        z_dot = u*np.sin(theta) + w*np.cos(theta)

        return np.array([u_dot,w_dot,q_dot,theta_dot,x_dot,z_dot],dtype=float)
    
    
    







        
        











        













