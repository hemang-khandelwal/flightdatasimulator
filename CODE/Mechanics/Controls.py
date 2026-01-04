import numpy as np 

class Controls:
    def __init__(self,mode):
        self.mode = mode

        ## Manual Forced Controls 
        self.manualElevator = 0.0 
        self.manualThrust = 0.0
        self.schedule = ControlSchedule()

    def elevator(self,t):
        if self.mode == "scheduled":
            return self.schedule.getInputs(t)[0]
        else: 
            return self.manualElevator

    def thrust(self,t):
        if self.mode == "scheduled":
            return self.schedule.getInputs(t)[1]
        else: 
            return self.manualThrust
    
    def getInputs(self,t):
        return 



class ControlSchedule:
    def __init__(self):
        self.events = []

    # Storing a control action 
    # Each item in the list one event 
    def addEvent(self, start, end, elevator, thrust):
        self.events.append({
            "TimeStart" : start,
            "TimeEnd" : end, 
            "Elevator" : elevator,
            "Thrust" : thrust 
        })

    def clearEvents(self):
        # Remove all scheduled events while keeping the same schedule instance
        self.events.clear()

    "Returns what the controls should be at a given time"
    def getInputs(self, t):
        elevator = 0.0
        thrust = 0.0
        for event in self.events: 
            # Allows overriding of event        
            if event["TimeStart"] <= t <= event["TimeEnd"]:
                elevator = event["Elevator"]
                thrust = event["Thrust"]
        return elevator, thrust 
