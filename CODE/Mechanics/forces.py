import os 
import numpy as np 
from Database.Environment import ISA

class Forces:
    def __init__(self,aeroModel,surfaceArea,chord):
        self.surfaceArea = surfaceArea
        self.aeroModel = aeroModel ## Passes the regression module here, this is imported from the main file 
        self.chord = chord 

    # QUASI-STEADY AERODYNAMICS 
    def aeroForces(self,density,resulantV,aoa, limit_aoa):
        ## This if statement is needed, as the Trim Solver needs to be allowed to explore non-physical states 
        ## This allows it to then converge at a physical state 
        ## However the RK4 Integrator working with Flight Dynamics cannot have non-physical states otherwise the numbers increase too quick 
        databaseAOA = aoa 

        if limit_aoa == True: 
            databaseAOA = np.clip(databaseAOA, np.deg2rad(-15), np.deg2rad(15))
        # Getting the coefficient values for the required AOA value 
        CL = self.aeroModel.aeroval(databaseAOA,"cl") 
        CD = self.aeroModel.aeroval(databaseAOA,"cd") 
        CM = self.aeroModel.aeroval(databaseAOA,"cm") 

        liftForce = 0.5*density*((resulantV)**2)*self.surfaceArea*CL
        dragForce = 0.5*density*((resulantV)**2)*self.surfaceArea*CD
        momentForce = 0.5*density*((resulantV)**2)*self.surfaceArea*self.chord*CM

        return liftForce, dragForce, momentForce

    def resolveForce(self,aoa,force,direction):
        # Resolving the Lift, Drag, Moment Force into a horizontal/vertical direction as asked 
        if direction.upper() == "cos":
            force = force*np.cos(aoa)
        else: 
            force = force*np.sin(aoa)
        
        return force 
    

        

        

