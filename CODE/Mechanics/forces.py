import os 
import numpy as np 
from Database.Environment import ISA

class Forces:
    def __init__(self,aeroModel,surfaceArea,chord):
        self.surfaceArea = surfaceArea
        self.aeroModel = aeroModel ## Passes the regression module here, this is imported from the main file 
        self.chord = chord 

    def aeroForces(self,density,resulantV,aoa):
        # Getting the coefficient values for the required AOA value 
        CL = self.aeroModel.aeroval(aoa,"cl")
        CD = self.aeroModel.aeroval(aoa,"cd")
        CM = self.aeroModel.aeroval(aoa,"cm")

        liftForce = 0.5*density*((resulantV)**2)*self.surfaceArea*CL
        dragForce = 0.5*density*((resulantV)**2)*self.surfaceArea*CD
        momentForce = 0.5 

        return liftForce, dragForce, momentForce

    def resolveForce(self,aoa,force,direction):
        # Convert AOA from degrees to Radians:
        aoa = aoa * (np.pi)/180 
        # Resolving the Lift, Drag, Moment Force into a horizontal/vertical direction as asked 
        if direction.upper() == "cos":
            force = force*np.cos(aoa)
        else: 
            force = force*np.sin(aoa)
        
        return force 
    

        

        

