from abc import ABC, abstractmethod
import numpy as np 
# Space State Vector: [ u, w, q, theta, x, z ]

""" Sensor is an Abstract Class """
""" Sensor cannot be instantiated on it's own and serves as a blueprint for other classes """
class Sensor(ABC): 
    def __init__(self,intensity, updateFrequency,noiseEnabled, distributionType): 
        self.intensity = intensity
        self.updateFrequency = updateFrequency # measured in Hz 
        self.noiseEnabled = noiseEnabled
        self.distributionType = distributionType

        self.updateTimePeriod = 1/updateFrequency # T = 1/F
        self.timeElapsedSinceLastReading = 0
        self.lastReading = 0 
  

    #Encapsulation - Internal Use Only by the Class 
    def _noise(self):
        if not self.noiseEnabled: 
            return 0
        
        if self.distributionType.upper() == "GAUSSIAN" or self.distributionType.upper() == "NORMAL":
            return np.random.normal(0,self.intensity) # Standard Normal Distribution with Mean 0 
        elif self.distributionType.upper() == "UNIFORM": 
            return np.random.uniform(-self.intensity,self.intensity)
        else: 
            # Input argument of correct type but inappropriate value
            raise ValueError(f"Unknown noise distribution: {self.distributionType}")

    ## EVERY SENSOR MUST DEFINE HOW IT MEASURES TRUE STATE 
    ## Does not allow instantiate of a half-defined sensor 
    ## Used for good practice  
    @abstractmethod
    def _trueState(self,trueState, stateDerivative):
        #Return the noise-free reading for this sensor
        raise NotImplementedError
    

    ## Returns reading from sensor 
    def measure(self,trueState, stateDerivative, dt): 
        self.timeElapsedSinceLastReading += dt 
        if self.timeElapsedSinceLastReading >= self.updateTimePeriod: 
            # Retrieves the true value from the Dynamics Model (State Space Vecotr or State Derivatives)
            trueValue = self._trueState(trueState, stateDerivative) 
            self.timeElapsedSinceLastReading = 0 
            noise = self._noise()
            self.lastReading = trueValue + noise 
        return self.lastReading

    
class AttitudeSensor(Sensor):
    def __init__(self, intensity, updateFrequency, noiseEnabled, distributionType):
        super().__init__(intensity, updateFrequency, noiseEnabled, distributionType)

    def _trueState(self,trueState, stateDerivative):
        return trueState[3]
    

class Altimeter(Sensor):
    def __init__(self, intensity, updateFrequency, noiseEnabled, distributionType):
        super().__init__(intensity, updateFrequency, noiseEnabled, distributionType)
    def _trueState(self,trueState, stateDerivative):
        return trueState[5]
    

class PitotTube(Sensor):
    def __init__(self, intensity, updateFrequency, noiseEnabled, distributionType):
        super().__init__(intensity, updateFrequency, noiseEnabled, distributionType)

    def _trueState(self,trueState, stateDerivative):
        u = trueState[0]
        w = trueState[1]
        return np.sqrt(u**2 + w**2)
    
class Accelerometer(Sensor):
    def __init__(self, intensity, updateFrequency, noiseEnabled, distributionType):
        super().__init__(intensity, updateFrequency, noiseEnabled, distributionType)

    def _trueState(self, trueState, stateDerivative):
        if stateDerivative is None:
            raise ValueError("StateDerivative required for accelerometer") # Exception handling 
        # Uses vertical acceleration from the state derivative
        return stateDerivative[1]


"""### Sensor Manager ### """
# An easy Interface to collate all the sensors

class SensorManager:
    def __init__(self):
        self.sensors = {} # Dictionary Stores all the sensors 

    # Creating the Dictionary of Sensors 
    def addSensor(self, name, sensor):
        self.sensors[name] = sensor 
        # sensor is an object which is instantiated 

    def allSensorReadings(self,trueState,stateDerivative, dt):
        measurements = {} 
        for name, sensor in self.sensors.items():
            measurements[name] = sensor.measure(trueState,stateDerivative,dt)
        return measurements

    

    


