import numpy as np 

""" State Estimating : [u,w,theta,z] - These are the states the sensors measure """
class Kalman4d:
    def __init__(
            self,
            initialStateEstimate, # Initial Guess of the real state 
            initialUncertainityEstimate, # The uncertainity from that initial guess [4x4 Matrix]
            processNoiseUncertainity, # How much the dynamics model is trusted 
            sensorNoiseUncertainity # How noisy the filter believes the sensors are 
    ):

        # State Vector Estimate at any given time 
        self.stateEstimate = np.array(initialStateEstimate, dtype=float).reshape(4,1)

        #Estimate of Covariance Matrix of Uncertainity (4x4)
        self.estimateUncertainity = np.array(initialUncertainityEstimate, dtype = float)

        #Model Uncertainity (4x4)
        self.modelUncertainity = np.array(processNoiseUncertainity, dtype = float)

        #Sensor Uncertainity (4x4)
        self.sensorUncertainity = np.array(sensorNoiseUncertainity,dtype=float)

        # Identity matrix (4x4)
        self.identity = np.eye(4)

        # Difference in Sensor Readings and True State 
        self.kalmanResiduals = []


    """  
    PREDICTION STEP (Time Update)

    General Kalman prediction equations:

        x̂ₖ|ₖ₋₁ = Fₖ · x̂ₖ₋₁|ₖ₋₁
        Pₖ|ₖ₋₁ = Fₖ · Pₖ₋₁|ₖ₋₁ · Fₖᵀ + Qₖ
    """

    """ Predicting the next state and uncertainity with no use of new sensor data"""
    def predict(self,timeStep):
       
        # Fₖ → State transition matrix
        # For a constant-state model: Fₖ = I
        stateTransition = np.eye(4)

        """ Predict next state estimate with no control input
        x̂ₖ|ₖ₋₁ = Fₖ · x̂ₖ₋₁|ₖ₋₁ """
        self.stateEstimate = stateTransition @ self.stateEstimate

        """  Increase uncertainty due to process noise (replicating an imperfect model)
        Pₖ|ₖ₋₁ = Fₖ · Pₖ₋₁|ₖ₋₁ · Fₖᵀ + Qₖ """
         
        self.estimateUncertainity = (
            (stateTransition @ self.estimateUncertainity @ stateTransition.T)
            + self.modelUncertainity*timeStep
            )
    
    """ Correcting the prediction with reality (measured from sensors)"""
    def update(self,sensorMeasurements):
        
        """Convert all sensor readings to coloumn vector 
         sensors = [velocityMeasured,accelerationMeasured,attitudeMeasured,alitutdeMeasured]"""
        measurements = np.array(sensorMeasurements,dtype=float).reshape(4,1)

        """ Hₖ is the Measurement matrix
         Direct measurement of state:  Hₖ = I """
        
        measurementMatrix = np.eye(4)

        """ 
        yₖ = zₖ - Hₖ · x̂ₖ|ₖ₋₁
        Innovation =  Residual to measure how wrong the prediction was """

        innovation = measurements - (measurementMatrix @ self.stateEstimate)

        """ Sₖ = Hₖ · Pₖ|ₖ₋₁ · Hₖᵀ + Rₖ
       Innovation uncertainty  = How noisy is the disagreement between predicted and measured states"""
        
        innovationUncertainity = (measurementMatrix 
                                  @ self.estimateUncertainity
                                  @ measurementMatrix.T
                                  + self.sensorUncertainity)
        
        """ Kₖ = Pₖ|ₖ₋₁ · Hₖᵀ · Sₖ⁻¹
         Kalman gain = How strongly should the program make the correction """
        
        kalmanGain = (self.estimateUncertainity
                      @ measurementMatrix.T
                      @ np.linalg.inv(innovationUncertainity))
        
        """  x̂ₖ|ₖ = x̂ₖ|ₖ₋₁ + Kₖ · yₖ
         Correcting the predicted state using sensor data """
        
        self.stateEstimate = self.stateEstimate + kalmanGain @ innovation

        """ Pₖ|ₖ = (I - Kₖ · Hₖ) · Pₖ|ₖ₋₁
         Reduce uncertainty after incorporating measurements, increasing confidence in data """
        self.estimateUncertainity = (
            (self.identity - kalmanGain @ measurementMatrix)
            @ self.estimateUncertainity
        )

        """ Store the residuals allowing for user analysis"""
        self.kalmanResiduals.append(innovation.flatten())

        return innovation.flatten() 
    
    
    



        




    


