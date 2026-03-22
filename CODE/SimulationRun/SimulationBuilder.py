import numpy as np
from Database.AircraftData import AircraftData
from Database.BaseAeroModel import AeroModel
from Database.Environment import ISA
from Mechanics.Forces import Forces
from Mechanics.Dynamics import AircraftDynamics
from Mechanics.Integrator import RK4
from Mechanics.Controls import Controls, ControlSchedule
from Sensors.KalmanFilter import Kalman4d

from Perfomance.BlendedAeroModel import BlendedAeroModel
from Perfomance.StallManager import Stall


class SimulationBuilder:
    @staticmethod
    def build(config):
        """
        Creates and returns all domain objects required for the simulation.
        This is based purely on the user configuration.
        """

        domain = {}

        # Build Environment
        environment_id = config.get("environmentId") or config.get("EnvironmentID")
        weather_id = config.get("weatherId") or config.get("WeatherID")
        sim_id = config.get("simId") or config.get("SimID")

        if environment_id is not None and weather_id is not None:
            environment = ISA(EnvironmentID=environment_id, WeatherID=weather_id)
        elif sim_id is not None:
            environment = ISA(SimID=sim_id)
        else:
            raise KeyError("config must provide either 'simId' or both 'environmentId' and 'weatherId' for ISA lookup")
        domain["environment"] = environment

        # Build Aerodynamics Model
        aircraft_id = config["aircraftId"]
        regime_id = config.get("regimeId", 1)
        regression_degree = config.get("regressionDegree", 6)
        blend_width = config.get("blendWidth", np.deg2rad(5))
        decay_constant = config.get("decayConstant", 1.0)

        # Use AircraftData module to get aircraft-specific geometry/performance values
        aircraft_data = AircraftData.from_aircraft_id(aircraft_id)

        surface_area = aircraft_data.wingArea()
        if surface_area is None:
            surface_area = config.get("surfaceArea")

        chord = aircraft_data.aerodynamicChord()
        if chord is None:
            chord = config.get("chord")

        if surface_area is None or chord is None:
            raise KeyError("Aircraft data must provide 'wingArea' and 'aerodynamicChord' for Forces")

        base_aero = AeroModel(aircraft_id, regime_id, regression_degree)
        aero = BlendedAeroModel(base_aero, blend_width, decay_constant)
        domain["aero"] = aero
        domain["aircraft_data"] = aircraft_data

        # Build Forces
        forces = Forces(aero, surface_area, chord)
        domain["forces"] = forces

        # Build Controls
        control_mode = config.get("controlMode", config.get("ControlMode", "manual"))
        controls = Controls(mode=control_mode)
        if control_mode == "scheduled":
            schedule = ControlSchedule()
            for event in config.get("controlSchedule", []):
                schedule.addEvent(
                    event["start"],
                    event["end"],
                    event["elevator"],
                    event["thrust"],
                )
            controls.schedule = schedule
        domain["controls"] = controls

        # Build dynamics + integrator
        dynamics = AircraftDynamics(environment, aero, forces, controls, aircraft_data=aircraft_data)
        integrator = RK4(dynamics)
        domain["integrator"] = integrator

        # Build Stall
        stall = None
        if config.get("UseStall", config.get("useStall", False)):
            stall = Stall(
                config["criticalAoa"],
                config["stallMargin"],
                aero,
                environment,
                forces,
            )
        domain["stall"] = stall

        # Sensors / Kalman (optional)
        domain["sensors"] = config.get("sensors")

        domain["kalman"] = None
        kalman_cfg = config.get("kalman")
        if kalman_cfg:
            domain["kalman"] = Kalman4d(
                kalman_cfg["initialStateEstimate"],
                kalman_cfg["initialUncertainityEstimate"],
                kalman_cfg["processNoiseUncertainity"],
                kalman_cfg["sensorNoiseUncertainity"],
            )

        return domain

