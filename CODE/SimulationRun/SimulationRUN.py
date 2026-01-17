import sys
from pathlib import Path

import numpy as np

# Ensure project root is on sys.path when run as a script
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from SimulationRun.SimInfo import SimInfo
from SimulationRun.SimEngine import SimEngine
from SimulationRun.SimModules import (
    SimControls,
    SimDynamics,
    SimKalmanFilter,
    SimLogger,
    SimSensors,
    SimStall,
    SimTruthMeasurement,
)

class SimulationRun:
    @ staticmethod

    def create(config,controls,integrator,sensors,kalman,stall):
        dt = config["dt"]
        initialState = np.array(config["initialState"],dtype= float)
        # The Kalman filter tracks a reduced state [u, w, theta, z]
        kalman_state = (
            initialState[[0, 1, 3, 5]] if initialState.size >= 6 else initialState.copy()
        )

        ctx = SimInfo(
            t = 0.0,
            dt= dt,
            trueState = initialState,
            stateEstimate = kalman_state,
            stateDerivative=None,
            measurement=None
        )

        log = [] 
        modules = [] 

        # Controls First 
        modules.append(SimControls(controls))
        modules.append(SimDynamics(integrator))

        # Sensors / measurement source
        if sensors is not None:
            modules.append(SimSensors(sensors))
        else:
            modules.append(SimTruthMeasurement())

        # Kalman runs after measurement producer
        if kalman is not None:
            modules.append(SimKalmanFilter(kalman))

        if stall is not None: 
            modules.append(SimStall(stall))

        modules.append(SimLogger(log))

        engine = SimEngine(ctx,modules)
        engine.log  = log

        return engine 
    




