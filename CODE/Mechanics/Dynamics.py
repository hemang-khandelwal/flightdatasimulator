import numpy as np 
# Space State Vector: [ u, w, q, theta, x, z ]

class AircraftDynamics:
    def __init__(self, environment, aeroModel, forces, controls): # Pass in Aircraft Module in later 
        # Passing the objects into the class 
    ######## Get these aircraft specific values from Aircraft Object later 
        #self.aircraft = aircraft 
        self.surfaceArea = 2 ## CHANGE, call this from aircraft database structure
        self.chord = 34 ### CHANGE, call this from aircraft database structure 
        self.cmDeltaE = -1.28
        self.cdDeltaE = 0.060
        self.clDeltaE = 0.430
    ##############
        self.environment = environment
        self.aeroModel = aeroModel
        self.forces = forces 
        self.controls = controls
        self.stateVector = []


    def stateDerivatives(self,t, state): 
        # Unpacking the SSV (State Space Vector)
        u, w, q, theta, x, z = state 
        # Theta = pitch 

        resultantV = np.sqrt(u**2 + w**2)
        gamma = np.arctan2(w,u) # Gamma = Flight Path Angle 

        aoa = theta - gamma

        L,D,M = self.forces.aeroForces(
            self.environment.density(z), # The vertical height(Z) is the elevation 
            resultantV,
            aoa
        )
        ## Adjusting for control input 
        dynamicPressure = 0.5*self.environment.density(z)*((resultantV)**2)*self.surfaceArea

        L = L + dynamicPressure*(self.clDeltaE * self.controls.elevator())
        D = D + dynamicPressure* (self.cdDeltaE * self.controls.elevator())
        M = M + dynamicPressure*self.chord*(self.cmDeltaE * self.controls.elevator())

        T = self.controls.thrust()
    
        ## Resolving Forces 
        horiz = (self.forces.resolveForce(aoa,L,"sin")) -(self.forces.resolveForce(aoa,D,"cos")) + T 
        vert = (self.forces.resolveForce(aoa,L,"cos"))  -(self.forces.resolveForce(aoa,D,"sin")) 

        m = 1157
        Iy = 1346
        g = 9.81

        theta_dot = q

        ## Equations of Motion 
        ## ACCELERATION
        u_dot = (horiz / m) - g*np.sin(theta) + w*q
        w_dot = (vert / m) - g*np.cos(theta) - u*q
        q_dot = M / Iy

        ## Kinematic Definitions 
        # Velocity 
        x_dot = u*np.cos(theta) - w*np.sin(theta)
        z_dot = u*np.sin(theta) + w*np.cos(theta)

        return np.array([u_dot,w_dot,q_dot,theta_dot,x_dot,z_dot],dtype=float)
    
    
    







        
        











        













