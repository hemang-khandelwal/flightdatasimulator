
import numpy as np 

import sys
from pathlib import Path

# Make project modules importable when running this file directly
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from SimulationRun.SimulationBuilder import SimulationBuilder
from SimulationRun.SimulationRUN import SimulationRun
from UnitTesting.config_template import FULL_CONFIG


def run_from_config(cfg):
    domain = SimulationBuilder.build(cfg)
    engine = SimulationRun.create(
        cfg,
        domain["controls"],
        domain["integrator"],
        domain["sensors"],
        domain["kalman"],
        domain["stall"],
    )
    engine.run(cfg.get("timeEnd", 5.0))
    return engine


if __name__ == "__main__":
    config = FULL_CONFIG.copy()
    # tweak any values here if needed, e.g.:
    # config["controlMode"] = "manual"
    # config["kalman"] = None
    engine = run_from_config(config)

    print("=== Simulation complete ===")
    print("Final time:", engine.ctx.t)
    print("Final true state:", engine.ctx.trueState)
    print("Final estimated state:", engine.ctx.stateEstimate)
    print("Logged samples:", len(engine.log))
    if engine.log:
        print("First log entry:", engine.log[0])
        print("Last log entry:", engine.log[-1])
