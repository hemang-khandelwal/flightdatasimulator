



import os 



class Mechanics:
    def __init__(self,aero_Model,surfaceArea,chord):
        self.surfaceArea = surfaceArea
        self.aero_model = aero_Model ## Passes the regression algorithm into the module 
        self.chord = chord 

    def aeroForces(self,density,resulantV,aoa):
        CL = self.aero_model.aeroval(aoa,"cl")
        CD = self.aero_model.aeroval(aoa,"cd")
        CM = self.aero_model.aeroval(aoa,"cm")

        liftForce = 0.5*density*((resulantV)**2)*self.surfaceArea*CL
        dragForce = 0.5*density*((resulantV)**2)*self.surfaceArea*CD
        momentForce = 0.5 

        return liftForce, dragForce, momentForce

