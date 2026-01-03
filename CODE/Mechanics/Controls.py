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



class ControlSchedule:
    def __init__(self):
        self.events = []

    def add_event(self, start, end, elevator, thrust):
        self.events.append((start, end, elevator, thrust))

    def get_inputs(self, t):
        for start, end, e, thr in self.events:
            if start <= t <= end:
                return e, thr
        return 0.0, 0.0
