from abc import ABC, abstractmethod
import numpy as np
from SimulationRun.SimInfo import SimInfo


class SimModule(ABC):
    def initialise(self, ctx: SimInfo) -> None:
        # This will be run once every time a simulation is made
        return

    @abstractmethod
    def step(self, ctx: SimInfo) -> None:
        # This will be called at every timestep interval
        raise NotImplementedError


class SimControls(SimModule):
    def __init__(self, controls):
        super().__init__()
        self.controls = controls

    def step(self, ctx: SimInfo):
        # There will be seperate calls per channels
        ctx.elevator = self.controls.elevator(ctx.t)
        ctx.thrust = self.controls.thrust(ctx.t)


class SimDynamics(SimModule):
    def __init__(self, integrator):
        super().__init__()
        self.integrator = integrator

    def step(self, ctx: SimInfo):
        # Advance the dynamics model
        new_state = self.integrator.timeStep(ctx.t, ctx.trueState, ctx.dt)
        # Derivative corresponding to the updated state (at t + dt)
        ctx.stateDerivative = self.integrator.dynamics.stateDerivatives(
            ctx.t + ctx.dt, new_state
        )
        ctx.trueState = new_state


class SimSensors(SimModule):
    def __init__(self, sensors):
        super().__init__()
        self.sensors = sensors

    def step(self, ctx: SimInfo):
        if hasattr(self.sensors, "measure"):
            ctx.measurement = self.sensors.measure(
                ctx.trueState, ctx.stateDerivative, ctx.dt
            )
        elif hasattr(self.sensors, "allSensorReadings"):
            ctx.measurement = self.sensors.allSensorReadings(
                ctx.trueState, ctx.stateDerivative, ctx.dt
            )
        else:
            raise TypeError("sensors object must expose measure(...) or allSensorReadings(...)")


class SimTruthMeasurement(SimModule):
    """Fallback measurement module: uses true state slice when no sensors are provided."""

    def step(self, ctx: SimInfo) -> None:
        state = np.array(ctx.trueState).flatten()
        if state.size >= 6:
            ctx.measurement = state[[0, 1, 3, 5]]
        else:
            ctx.measurement = state.copy()


class SimKalmanFilter(SimModule):
    def __init__(self, kalman):
        super().__init__()
        self.kalman = kalman

    def initialise(self, ctx: SimInfo) -> None:
        ctx.stateEstimate = self.kalman.stateEstimate.flatten()

    def step(self, ctx: SimInfo):
        if ctx.measurement is None:
            return
        if isinstance(ctx.measurement, dict):
            measurement = np.array(list(ctx.measurement.values()), dtype=float)
        else:
            measurement = np.array(ctx.measurement, dtype=float).flatten()
        # Predict forward then correct with the latest measurement
        self.kalman.predict(ctx.dt)
        self.kalman.update(measurement)
        ctx.stateEstimate = self.kalman.stateEstimate.flatten()


class SimStall(SimModule):
    def __init__(self, stall):
        super().__init__()
        self.stall = stall

    def step(self, ctx: SimInfo):
        # Passing in the true State to determine whether it is stalled or not
        ctx.stalled = self.stall.isStateStall(ctx.trueState)


class SimLogger(SimModule):
    def __init__(self, logList):
        super().__init__()
        self.logList = logList

    def step(self, ctx: SimInfo):
        self.logList.append({
            "Time": ctx.t,
            "True State": None if ctx.trueState is None else np.array(ctx.trueState),
            "Estimated State": None if ctx.stateEstimate is None else np.array(ctx.stateEstimate),
            "Elevator": ctx.elevator,
            "Thrust": ctx.thrust,
            "Stall": ctx.stalled,
        })
