## Custom Algorithm ##
import numpy as np 

def smoothening(x):
    x = max(0.0,min(1.0,x)) # Cap the output to 1 as the function can only return 1 
    return x*x * (3 - 2*x)


class BlendedAeroModel:
    def __init__(self, baseAeroModel,blendWidth, decayConstant):
        self.baseAero = baseAeroModel
        self.blendWidth = blendWidth
        self.alphaCritical = np.deg2rad(20)
        self.decayConstant = decayConstant

        self.criticalCl = self.baseAero.aeroval(self.alphaCritical,"cl")
        self.criticalCd = self.baseAero.aeroval(self.alphaCritical,"cd")
        self.criticalCm = self.baseAero.aeroval(self.alphaCritical,"cm")


    def _blendingFactor(self,alpha): 
        """
        0 = fully pre-stall model 
        1 = fully post-stall model 
        """

        a = abs(alpha)  
        ## Distance past Stall / Blend Width 
        factor = (a- self.alphaCritical) / max(self.blendWidth,1e-6)
        return smoothening(factor)
    

    def _postStallCL(self,alpha):
        a = abs(alpha)
        excess = max(0.0,a-self.alphaCritical)

        ## Exponential Decay Model 

        cl = self.criticalCl * np.exp(-self.decayConstant * excess)

        return np.sign(alpha) * abs(cl)

    def _postStallCD(self,alpha):
        a = abs(alpha)
        excess = max(0.0,a-self.alphaCritical)

        ## Quadratic Growth 
        return self.criticalCd + 1.5*excess**2
 
    """Aircraft should pitch nose-down. This helps natural recovery, preventing infinite AoA"""
    def _postStallCM(self,alpha):
        a = abs(alpha)
        excess = alpha - np.sign(alpha) * self.alphaCritical
        return self.criticalCm - 0.5 * excess
        
    def aeroval(self,alpha,coeff):
        blendFactor = self._blendingFactor(alpha)

        if coeff == "cl":
            preStall = self.baseAero.aeroval(alpha,"cl")
            postStall = self._postStallCL(alpha)
        elif coeff == "cd":
            preStall = self.baseAero.aeroval(alpha,"cd")
            postStall = self._postStallCD(alpha)
        elif coeff == "cm":
            preStall = self.baseAero.aeroval(alpha,"cm")
            postStall = self._postStallCM(alpha)
        else: 
            return ValueError("Unknown coefficient")
        
        return (1-blendFactor)*preStall + (blendFactor * postStall)
    
        
    
    

        








    
