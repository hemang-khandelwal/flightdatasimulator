import numpy as np 

# Finds the conditions required for steady-level flight 
class TrimSolver:
    def __init__(self,dalpha, de, toleration, maxIterations, aeroModel, environment, forces, controls):
        self.dalpha = dalpha  
        self.toleration = toleration
        self.maxIterations = maxIterations
        self.de = de 
        self.aeroModel = aeroModel
        self.environment = environment
        self.forces = forces 
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
       
    def equationsOfMotion(self,aoa,e,u,w,z,q):
         # Gamma = Flight Path Angle 
        resultantV = np.sqrt(u**2 + w**2)
        gamma = np.arctan2(w,u) # Gamma = Flight Path Angle 

        theta = aoa + gamma 

        L,D,M = self.forces.aeroForces(
            self.environment.density(z), # The vertical height(Z) is the elevation 
            resultantV,
            aoa
        )

        ## Adding control effect to the coefficient values 
        dynamicPressure = 0.5*self.environment.density(z)*((resultantV)**2)*self.surfaceArea

        L = L + dynamicPressure*(self.clDeltaE * e)
        D = D + dynamicPressure* (self.cdDeltaE * e)
        M = M + dynamicPressure*self.chord*(self.cmDeltaE * e)

        ## Resolving for Vertical Forces 
        vert = (self.forces.resolveForce(aoa,L,"cos"))  -(self.forces.resolveForce(aoa,D,"sin")) 

        m = 1157
        Iy = 1346
        g = 9.81

        ## Equations of Motion 
        ## ACCELERATION 
        w_dot = (vert / m) - g*np.cos(theta) - u*q
        q_dot = M / Iy


        ####
        F = np.array([w_dot,q_dot])
        ###

        return F 
    
    def dw_dot_dalpha(self,aoa,e,u,w,z,q):
        aoa1 = aoa - self.dalpha
        aoa2 = aoa + self.dalpha

        w_dot1 = self.equationsOfMotion(aoa1,e,u,w,z,q)[0]
        w_dot2 = self.equationsOfMotion(aoa2,e,u,w,z,q)[0]

        return (w_dot2-w_dot1)/(2*self.dalpha)
    
    def dw_dot_de(self,aoa,e,u,w,z,q):
        e1 = e - self.de
        e2 = e + self.de

        w_dot1 = self.equationsOfMotion(aoa,e1,u,w,z,q)[0]
        w_dot2 = self.equationsOfMotion(aoa,e2,u,w,z,q)[0]

        return (w_dot2-w_dot1)/(2*self.de)
    

    def dq_dot_dalpha(self,aoa,e,u,w,z,q):
        aoa1 = aoa - self.dalpha
        aoa2 = aoa + self.dalpha

        w_dot1 = self.equationsOfMotion(aoa1,e,u,w,z,q)[1]
        w_dot2 = self.equationsOfMotion(aoa2,e,u,w,z,q)[1]

        return (w_dot2-w_dot1)/(2*self.dalpha)
    
    def dq_dot_de(self,aoa,e,u,w,z,q):
        e1 = e - self.de
        e2 = e + self.de

        w_dot1 = self.equationsOfMotion(aoa,e1,u,w,z,q)[1]
        w_dot2 = self.equationsOfMotion(aoa,e2,u,w,z,q)[1]

        return (w_dot2-w_dot1)/(2*self.de)

    def jacobianMatrix(self, aoa, e, u, w, z, q):
        return np.array([
            [
                self.dw_dot_dalpha(aoa, e, u, w, z, q),
                self.dw_dot_de(aoa, e, u, w, z, q)
            ],
            [
                self.dq_dot_dalpha(aoa, e, u, w, z, q),
                self.dq_dot_de(aoa, e, u, w, z, q)
            ]
        ])
    
    def newtonRapshon(self,alpha0,e0,u,w,z,q):
        aoa = alpha0
        e = e0 

        w_dot, q_dot = self.equationsOfMotion(aoa,e,u,w,z,q)
        iterations = 1

        while abs(w_dot) > self.toleration or abs(q_dot) > self.toleration and iterations < self.maxIterations:
            
            # Where w_dot & q_dot = f1,f2 respectively 
            w_dot, q_dot = self.equationsOfMotion(aoa,e,u,w,z,q) 

            # Compute Jacobian Matrix 
            J = self.jacobianMatrix(aoa,e,u,w,z,q)

            detJ = J[0,0]*J[1,1] - J[0,1]*J[1,0] # Finding the determinant of the Matrix 

            # Calculating Newton Raphson Correction temrs 
            # Thus JF​(xn​)(xn+1​−xn​)=−F(xn​)
            # Where (xn+1-xn) = Changeinx
            # Where x = [w_dot,q_dot]
    
            changeInAOA = (-J[1,1]*w_dot + J[0,1]*q_dot) / detJ
            changeInElevator   = ( J[1,0]*w_dot - J[0,0]*q_dot) / detJ

            aoa += changeInAOA
            e   += changeInElevator

            w_dot, q_dot = self.equationsOfMotion(aoa, e, u, w, z, q)

            iterations += 1




