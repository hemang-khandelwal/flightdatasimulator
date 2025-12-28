import numpy as np 

class Controls:
    def __init__(self, elevator=0.0, thrust=0.0):
        self._elevator = elevator
        self._thrust = thrust

    def elevator(self):
        #return self._elevator
        return self._elevator

    def thrust(self):
        return self._thrust
