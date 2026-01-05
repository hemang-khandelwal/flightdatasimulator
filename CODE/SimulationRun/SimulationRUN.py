import numpy as np 
from SimulationRun.SimInfo import SimInfo
from SimulationRun.SimEngine import SimEngine

from SimulationRun.SimModules import SimControls
from SimulationRun.SimModules import SimDynamics
from SimulationRun.SimModules import SimKalmanFilter
from SimulationRun.SimModules import SimSensors
from SimulationRun.SimModules import SimStall
from SimulationRun.SimModules import SimLogger

class SimulationRun:
    @ staticmethod

    def create(config,controls,integrator,sensors,kalman,stall):
        dt = config["dt"]
        initialState = np.array(config["initialState"],dtype= float)

        ctx = SimInfo(
            t = 0.0,
            dt= dt,
            trueState = initialState,
            stateEstimate = initialState.copy()
        )

        log = [] 
        modules = [] 

        # Controls First 
        modules.append(SimControls(controls))
        modules.append(SimDynamics(integrator))

        # If there are no sensors present the measurement equals the truth so the Kalman can still run 
        if sensors is not None: 
            modules.append(SimSensors(sensors))
        else: 
            ctx.measurement =  ctx.trueState.copy()
        
        # This ensures the sensors always runs before the Kalman. 
        # If there are no sensors present then ctx.measurement is already set 
        if kalman is not None: 
            modules.append(SimKalmanFilter(kalman))
        else: 
            # If no Kalman, the estimate just tracks the truth 
            pass 

        if stall is not None: 
            modules.append(SimStall(stall))

        modules.append(SimLogger(log))

        engine = SimEngine(ctx,modules)
        engine.log  = log

        return engine 
    




