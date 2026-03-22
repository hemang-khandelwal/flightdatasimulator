import numpy as np 
# Space State Vector: [ u, w, q, theta, x, z ]

class AircraftDynamics:
    def __init__(self, environment, aeroModel, forces, controls, aircraft_data=None):
        self.aircraft_data = aircraft_data

        if self.aircraft_data is not None:
            wing_area = self.aircraft_data.wingArea()
            if wing_area is not None:
                self.surfaceArea = wing_area
            else:
                self.surfaceArea = forces.surfaceArea

            chord_value = self.aircraft_data.aerodynamicChord()
            if chord_value is not None:
                self.chord = chord_value
            else:
                self.chord = forces.chord
        else:
            self.surfaceArea = forces.surfaceArea
            self.chord = forces.chord

        self.cmDeltaE = -1.28
        self.cdDeltaE = 0.060
        self.clDeltaE = 0.430
        self.cmq = -12.4

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
        resultantV = max(resultantV, 1e-3)  # avoid divide-by-zero instabilities
        gamma = np.arctan2(w, u)  # Flight Path Angle

        aoa = theta - gamma
        aoa = np.clip(aoa, np.deg2rad(-30), np.deg2rad(30))

        L,D,M = self.forces.aeroForces(
            self.environment.density(z), # The vertical height(Z) is the elevation 
            resultantV,
            aoa,
            True # Asking whether theyre should be a cap to aoa 
        )
        ## Adjusting for control input 
        dynamicPressure = 0.5*self.environment.density(z)*((resultantV)**2)*self.surfaceArea

        # Positive elevator input should be nose-up: invert sign to match coefficient convention
        e_eff = -self.controls.elevator(t)
        L = L + dynamicPressure*(self.clDeltaE * e_eff)
        D = D + dynamicPressure* (self.cdDeltaE * e_eff)
        M = M + dynamicPressure*self.chord*(self.cmDeltaE * e_eff)


        ### ADDING PITCH DAMPENING ######
        q_hat = q * self.chord / (2 * resultantV)
        M = M + dynamicPressure * self.chord * (self.cmq * q_hat)

        ###################################
        T = self.controls.thrust(t)
    
        ## Resolving Forces 
        horiz = (self.forces.resolveForce(aoa,L,"sin")) -(self.forces.resolveForce(aoa,D,"cos")) + T 
        vert = (self.forces.resolveForce(aoa,L,"cos"))  -(self.forces.resolveForce(aoa,D,"sin")) 

        m = 770
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
    
    
    







        
        

























