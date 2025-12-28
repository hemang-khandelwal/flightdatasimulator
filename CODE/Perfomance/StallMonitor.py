class Stall:
    def __init__(self,criticalAOA,margin,aeroModel,environment,forces): 
        self.criticalAOA = criticalAOA
        self.margin = margin 
        self.aeroModel = aeroModel
        self.environment = environment
        self.forces = forces
        self.CLMAX = self.aeroModel.maxValue("cl")[1]
        self.mass = 770 # Get from Aircraft Info Table
     

    def isStall(self,aoa,elevation,resultantV):
        if aoa >= self.criticalAOA: # Checks if current aoa is above critical angle 
            return True
        # Checks if current Lift Coefficient is in promiximity of Max CL (Second Returned value from function aeroModel.maxValue)
        elif self.aeroModel.aeroval(aoa,"cl") >= self.margin*self.CLMAX:
            return True 
        # Checks if The Current Lift Force is Less than the Weight of the aircraft, as otherwise aircraft is falling
        elif self.forces.aeroForces(self.environment.density(elevation),resultantV,aoa,False)[0] < self.mass*9.81: 
            return True 
        else: 
            return False 
        







    
