import os 
import numpy as np 

class Mechanics:
    def __init__(self,aero_Model,surfaceArea,chord):
        self.surfaceArea = surfaceArea
        self.aero_model = aero_Model ## Passes the regression module here, this is imported from the main file 
        self.chord = chord 

    #def ISAModel(self):

    def aeroForces(self,density,resulantV,aoa):
        # Getting the coefficient values for the required AOA value 
        CL = self.aero_model.aeroval(aoa,"cl")
        CD = self.aero_model.aeroval(aoa,"cd")
        CM = self.aero_model.aeroval(aoa,"cm")

        liftForce = 0.5*density*((resulantV)**2)*self.surfaceArea*CL
        dragForce = 0.5*density*((resulantV)**2)*self.surfaceArea*CD
        momentForce = 0.5 

        return liftForce, dragForce, momentForce

    def resolveForce(self,aoa,force,direction):
        # Convert AOA from degrees to Radians:
        aoa = aoa * (np.pi)/180 
        # Resolving the Lift, Drag, Moment Force into a horizontal/vertical direction as asked 
        if direction.upper() == "H":
            force = force*np.cos(aoa)
        else: 
            force = force*np.sin(aoa)
        
        return force 
    

        

        

