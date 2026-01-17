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

