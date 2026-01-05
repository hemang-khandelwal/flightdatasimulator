from typing import List
import numpy as np 
from SimulationRun.SimInfo import SimInfo
from SimulationRun.SimModules import SimModule

class SimEngine:
    def __init__(self, ctx:SimInfo, modules: List[SimModule]):
        self.ctx = ctx
        self.modules = modules 
        self.log = [] 


        for m in self.modules:
            m.initialise(self.ctx)

    def step(self) -> None: 
        # Run the stepping 
        for m in self.modules: 
            m.step(self.ctx)

        
        # Advance forward in time 
        self.ctx.t += self.ctx.dt

    def run(self,timeEnd: float) -> None: 
        # No of Steps for the RK4 Integrator 
        # Total Time/change in time 
        # Total time is also the time it ends, saved as that as it's easier for Scheduling 
        noOfSteps = int(timeEnd/self.ctx.dt)

        for b in range(noOfSteps):
            self.step()


class SimControls(SimModule):
    def __init__(self,controls):
        super().__init__()
        self.controls = controls 


    def step(self,ctx: SimInfo):
        # There will be seperate calls per channels 
        ctx.elevator = self.controls.elevator(ctx.t)
        ctx.thrust = self.controls.thrust(ctx.t)

class SimDynamics(SimModule):
    def __init__(self, integrator):
        super().__init__()
        self.integrator = integrator
    
    def step(self, ctx:SimInfo):
        controlInput = {"Elevator": ctx.elevator, "Thrust": ctx.thrust}
        ctx.trueState = self.integrator.step(ctx.trueState,ctx.dt)

class SimSensors(SimModule):
    def __init__(self,sensors): 
        super().__init__()
        self.sensors = sensors 

    def step(self,ctx:SimInfo):
        ctx.measurement = self.sensors.measure(ctx.trueState)


class SimKalmanFilter(SimModule):
    def __init__(self,kalman):
        super().__init__()
        self.kalman = kalman 

    def initialise(self, ctx: SimInfo) -> None:
        ctx.stateEstimate = ctx.trueState.copy()
    
    def step(self,ctx:SimInfo):
        controlInput = {"Elevator": ctx.elevator, "Thrust": ctx.thrust}
        # The measurement must exist so the sensors should run before this module 
        ctx.stateEstimate = self.kalman.update(ctx.measurement,controlInput)


class SimStall(SimModule):
    def __init__(self,stall):
        super().__init__()
        self.stall = stall 

    def step(self,ctx:SimInfo):
        # Passing in the true State to determine whether it is stalled or not 
        ctx.stalled = self.stall.isStateStall(ctx.trueState)

class SimLogger(SimModule):
    def __init__(self,logList):
        super().__init__()
        self.logList = logList

    def step(self,ctx: SimInfo):
        self.logList.append({
            "Time": ctx.t
            "True State": np.array(ctx.trueState)
            "Estimated State" : np.array(ctx.stateEstimate)
            "Elevator": ctx.elevator
            "Thrust": ctx.thrust
            "Stall": ctx.stalled
        })






