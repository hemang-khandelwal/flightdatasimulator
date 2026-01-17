"""
Single place to see every config knob the pipeline expects/accepts.
Fill values as needed and pass the dict to SimulationBuilder.build(...).
"""

import numpy as np

# Full config example with sensible placeholders
FULL_CONFIG = {
    # Environment / aero database lookup
    "simId": 1,
    "aircraftId": 1,
    "regimeId": 1,
    "regressionDegree": 6,

    # Geometry for forces
    "surfaceArea": 122.0,
    "chord": 1.23,

    # Aerodynamic blending (post-stall model)
    "blendWidth": np.deg2rad(5),
    "decayConstant": 1.0,

    # Integrator / time
    "dt": 0.01,
    "timeEnd": 5.0,

    # Initial full state [u, w, q, theta, x, z]
    "initialState": [50.0, -2.0, 0.05, 0.10, 0.0, 1000.0],

    # Controls
    "controlMode": "scheduled",  # "manual" or "scheduled"
    "controlSchedule": [
        {"start": 0.0, "end": 1.0, "elevator": np.deg2rad(0), "thrust": 500.0},
        {"start": 1.0, "end": 3.0, "elevator": np.deg2rad(2), "thrust": 600.0},
        {"start": 3.0, "end": 5.0, "elevator": np.deg2rad(-1), "thrust": 550.0},
    ],

    # Stall monitoring
    "UseStall": True,
    "criticalAoa": np.deg2rad(17),
    "stallMargin": 0.95,

    # Kalman (optional). Measurements should be [u, w, theta, z] or a dict with those values.
    "kalman": {
        "initialStateEstimate": [50.0, -2.0, 0.10, 1000.0],
        "initialUncertainityEstimate": np.eye(4) * 0.5,
        "processNoiseUncertainity": np.eye(4) * 0.05,
        "sensorNoiseUncertainity": np.eye(4) * 0.2,
    },

    # Sensors (optional): provide an object, e.g., SensorManager with configured sensors
    # If omitted, measurements default to the true state slice used by the Kalman
    "sensors": None,

    # Trim solver (if you want to run it separately)
    "trimSolver": {
        "dalpha": np.deg2rad(0.05),
        "de": np.deg2rad(0.5),
        "toleration": 1e-6,
        "maxIterations": 2000,
        "alpha0Array": list(np.deg2rad(np.array([-5, -2, 0, 2, 5, 8, 12]))),
        "e0Array": list(np.deg2rad(np.array([-15, -10, -5, 0, 5, 10, 15]))),
        "toleranceDuplicate": 2,  # used to prune duplicate solutions
    },
}


def example_usage():
    """
    Quick sketch of how you might use the config with the builder/run.
    Replace SensorManager(...) and Kalman blocks with your actual objects/values.
    """
    from SimulationRun.SimulationBuilder import SimulationBuilder
    from SimulationRun.SimulationRUN import SimulationRun

    cfg = FULL_CONFIG.copy()
    domain = SimulationBuilder.build(cfg)
    engine = SimulationRun.create(
        cfg,
        domain["controls"],
        domain["integrator"],
        domain["sensors"],
        domain["kalman"],
        domain["stall"],
    )
    engine.run(cfg["timeEnd"])
    return engine
