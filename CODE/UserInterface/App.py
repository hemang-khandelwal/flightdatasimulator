"""
"""

from __future__ import annotations

import pyodbc 
import datetime
import json
import math
import sys
import traceback
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import tkinter as tk
import customtkinter as ctk

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from Database.AircraftData import AircraftData
except Exception:
    traceback.print_exc()
    AircraftData = None  # type: ignore

try:
    from SimulationRun.SimulationBuilder import SimulationBuilder
    from SimulationRun.SimulationRUN import SimulationRun
except Exception:
    traceback.print_exc()
    SimulationBuilder = None  # type: ignore
    SimulationRun = None  # type: ignore

try:
    from UserInterface.FlightTestDashboard import FlightTestDashboard, TelemetryCollector, TelemetrySnapshot
except Exception:
    traceback.print_exc()
    FlightTestDashboard = None  # type: ignore
    TelemetryCollector = None  # type: ignore
    TelemetrySnapshot = None  # type: ignore

try:
    from SimulationRun.EventIndexedDataLinking import EventLookup, SegmentIndexer
except Exception:
    traceback.print_exc()
    EventLookup = None  # type: ignore
    SegmentIndexer = None  # type: ignore

def _now_str() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _safe_float(value: str) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return None

class SimulationDatabase: 
    def __init__(self) -> None:
        try:
            self.conn = pyodbc.connect(
                "Driver={SQL Server};"
                "Server=localhost\\SQLEXPRESS;"
                "Database=Flight Simulator;"
                "Trusted_Connection=yes;"
            )
        except Exception:
            traceback.print_exc()
            self.conn = None

    def saveSim(self, cfg):
        if not self.conn:
            return None
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO Simulations(VersionID, Name, Description, AircraftID, EnvironmentID, WeatherID)
                OUTPUT INSERTED.SimID
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    int(cfg.get("versionId", 1)),
                    cfg.get("name", "Unnamed"),
                    cfg.get("description", ""),
                    cfg.get("aircraftId", 1),
                    cfg.get("environmentId", 1),
                    cfg.get("weatherId", 1),
                )
            )
            result = cursor.fetchone()
            if result is None:
                return None
            sim_id = int(result[0])
            cfg["simId"] = sim_id
            self.conn.commit()
            return sim_id
        except Exception as e:
            self.conn.rollback()
            print(f"DB save failed: {e}")
            return None

    def list_aircraft(self) -> List[Tuple[int, str]]:
        if not self.conn:
            return []
        cursor = self.conn.cursor()
        for label_col in ["Name", "AircraftType"]:
            try:
                cursor.execute(f"SELECT AircraftID, {label_col} FROM [dbo].[Aircraft] ORDER BY AircraftID")
                rows = cursor.fetchall()
                if rows:
                    return [(int(r[0]), str(r[1])) for r in rows]
            except Exception:
                continue
        return []

    def create_custom_aircraft(
        self,
        aircraft: Dict[str, Any],
        airfoil: Dict[str, Any],
        engine: Dict[str, Any],
        performance: Dict[str, Any],
        geometry: Dict[str, Any],
    ) -> Optional[int]:
        if not self.conn:
            return None

        cursor = self.conn.cursor()
        try:
            name = str(aircraft.get("Name", "")).strip()
            manufacturer = str(aircraft.get("Manufacturer", "")).strip()
            if not name:
                raise ValueError("Aircraft Name is required")

            # 1) Insert Aircraft, retrieve the generated AircraftID.
            aircraft_id: Optional[int] = None
            try:
                cursor.execute(
                    """
                    INSERT INTO [dbo].[Aircraft] (Name, Manufacturer)
                    OUTPUT INSERTED.AircraftID
                    VALUES (?, ?)
                    """,
                    (name, manufacturer),
                )
                res = cursor.fetchone()
                aircraft_id = int(res[0]) if res and res[0] is not None else None
            except Exception:
                cursor.execute(
                    """
                    INSERT INTO [dbo].[Aircraft] (Name)
                    OUTPUT INSERTED.AircraftID
                    VALUES (?)
                    """,
                    (name,),
                )
                res = cursor.fetchone()
                aircraft_id = int(res[0]) if res and res[0] is not None else None

            if aircraft_id is None:
                raise RuntimeError("Could not retrieve AircraftID")

            # 2) Insert Components row for this aircraft, retrieve generated ComponentID.
            component_id: Optional[int] = None
            try:
                cursor.execute(
                    """
                    INSERT INTO [dbo].[Components] (AircraftID)
                    OUTPUT INSERTED.ComponentID
                    VALUES (?)
                    """,
                    (aircraft_id,),
                )
                res = cursor.fetchone()
                component_id = int(res[0]) if res and res[0] is not None else None
                if component_id is None:
                    raise RuntimeError("Could not retrieve ComponentID")
            except Exception as exc:
                # A very common cause is a reversed FK: Components.ComponentID -> AirfoilData.ComponentID,
                # which would make inserting Components fail unless AirfoilData already has that ComponentID.
                msg = str(exc)
                if "FK_Components_AirfoilData" in msg:
                    raise RuntimeError(
                        "Database FK is backwards: `FK_Components_AirfoilData` makes `Components` depend on `AirfoilData`. "
                        "Fix in SSMS by dropping that FK and creating `AirfoilData(ComponentID)` -> `Components(ComponentID)`."
                    ) from exc
                raise RuntimeError(f"Components insert failed: {exc}") from exc

            # Sanity check: ensure the ComponentID we got actually exists (handles odd triggers/schema quirks).
            try:
                cursor.execute("SELECT COUNT(1) FROM [dbo].[Components] WHERE ComponentID = ?", (component_id,))
                exists = int(cursor.fetchone()[0])  # type: ignore[index]
            except Exception:
                exists = 1
            if exists == 0:
                cursor.execute(
                    "SELECT TOP 1 ComponentID FROM [dbo].[Components] WHERE AircraftID = ? ORDER BY ComponentID DESC",
                    (aircraft_id,),
                )
                row = cursor.fetchone()
                if row and row[0] is not None:
                    component_id = int(row[0])
                else:
                    raise RuntimeError("ComponentID lookup failed after insert")

            # AirfoilData (ComponentID is PK/FK)
            try:
                cursor.execute(
                    """
                    INSERT INTO [dbo].[AirfoilData] (
                        ComponentID, WingArea, AerodynamicChord, WingAirfoil,
                        HorizontalAirfoilAtRoot, HorizontalAirfoilAtTip,
                        AileronsDeflectionLimit, AileronsArea,
                        ElevatorDeflectionLimitMax, ElevatorDeflectionLimitMin, ElevatorArea,
                        RudderDeflectionLimit, FlapsArea, FlapsDeflectionLimit
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        component_id,
                        float(airfoil["WingArea"]),
                        float(airfoil["AerodynamicChord"]),
                        str(airfoil["WingAirfoil"]),
                        str(airfoil["HorizontalAirfoilAtRoot"]),
                        str(airfoil["HorizontalAirfoilAtTip"]),
                        float(airfoil["AileronsDeflectionLimit"]),
                        float(airfoil["AileronsArea"]),
                        float(airfoil["ElevatorDeflectionLimitMax"]),
                        float(airfoil["ElevatorDeflectionLimitMin"]),
                        float(airfoil["ElevatorArea"]),
                        float(airfoil["RudderDeflectionLimit"]),
                        float(airfoil["FlapsArea"]),
                        float(airfoil["FlapsDeflectionLimit"]),
                    ),
                )
            except Exception as exc:
                raise RuntimeError(f"AirfoilData insert failed: {exc}") from exc

            # EngineData
            cursor.execute(
                """
                INSERT INTO [dbo].[EngineData] (
                    ComponentID, ModelName, RatedPower, Displacement,
                    Height, Width, Length, SpecificFuelConsumption,
                    NoOfBlades, PropellerDiameter
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    component_id,
                    str(engine["ModelName"]),
                    float(engine["RatedPower"]),
                    float(engine["Displacement"]),
                    float(engine["Height"]),
                    float(engine["Width"]),
                    float(engine["Length"]),
                    float(engine["SpecificFuelConsumption"]),
                    int(engine["NoOfBlades"]),
                    float(engine["PropellerDiameter"]),
                ),
            )

            # PerformanceData (table name can vary in some deployments)
            perf_tables = ["PerformanceData", "PerfomanceData", "Performance", "Performance_Data"]
            perf_inserted = False
            for table in perf_tables:
                try:
                    cursor.execute(
                        f"""
                        INSERT INTO [dbo].[{table}] (
                            AircraftID, NormalMaxTakeOffWeight, UtilityMaxTakeOffWeight,
                            StallSpeed, CruiseSpeed, SeaLevelMaxSpeed, NeverExceedSpeed,
                            ServiceCeiling, TakeOffRun, LandingRun, EightyRange, SixtyRange
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            aircraft_id,
                            float(performance["NormalMaxTakeOffWeight"]),
                            float(performance["UtilityMaxTakeOffWeight"]),
                            float(performance["StallSpeed"]),
                            float(performance["CruiseSpeed"]),
                            float(performance["SeaLevelMaxSpeed"]),
                            float(performance["NeverExceedSpeed"]),
                            float(performance["ServiceCeiling"]),
                            float(performance["TakeOffRun"]),
                            float(performance["LandingRun"]),
                            float(performance["EightyRange"]),
                            float(performance["SixtyRange"]),
                        ),
                    )
                    perf_inserted = True
                    break
                except Exception:
                    continue
            if not perf_inserted:
                raise RuntimeError("Could not insert into PerformanceData table (name mismatch).")

            # Geometry
            cursor.execute(
                """
                INSERT INTO [dbo].[Geometry] (AircraftID, Length, Height, WheelBase, WheelTrack)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    aircraft_id,
                    float(geometry["Length"]),
                    float(geometry["Height"]),
                    float(geometry["WheelBase"]),
                    float(geometry["WheelTrack"]),
                ),
            )

            self.conn.commit()
            return aircraft_id
        except Exception:
            try:
                self.conn.rollback()
            except Exception:
                pass
            raise

    def _insert_sensor_noise(self, cursor, cfg) -> int:
        std_dev = 0.0
        frequency = 1.0 / float(cfg["dt"]) if float(cfg["dt"]) > 0 else 0.0
        enabled = 0

        kalman_cfg = cfg.get("kalman")
        if kalman_cfg:
            noise_matrix = kalman_cfg.get("sensorNoiseUncertainity")
            if noise_matrix:
                try:
                    std_dev = float(noise_matrix[0][0]) ** 0.5
                    enabled = 1 if std_dev > 0 else 0
                except Exception:
                    std_dev = 0.0

        cursor.execute(
            """
            INSERT INTO SensorNoise (Enabled, StdDev, Frequency)
            OUTPUT INSERTED.NoiseSimID
            VALUES (?, ?, ?)
            """,
            (enabled, std_dev, frequency),
        )
        result = cursor.fetchone()
        if result is None:
            raise RuntimeError("Could not retrieve NoiseSimID")
        return int(result[0])

    def _insert_trim_solver(self, cursor, cfg) -> int:
        trim_cfg = cfg.get("trimSolver", {})
        tolerance = float(trim_cfg.get("toleration", 1e-6))
        iterations = int(trim_cfg.get("maxIterations", 2000))

        cursor.execute(
            """
            INSERT INTO TrimSolver (Tolerance, Iterations)
            OUTPUT INSERTED.TrimSolverID
            VALUES (?, ?)
            """,
            (tolerance, iterations),
        )
        result = cursor.fetchone()
        if result is None:
            raise RuntimeError("Could not retrieve TrimSolverID")
        return int(result[0])
    
     
    def close(self):
        if self.conn:
            self.conn.close()



class FlightSimApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        self.title("Flight Dynamics Simulator")
        self.geometry("1280x860")
        self.configure(fg_color="#0b1220")

        self.data_dir = BASE_DIR / "UserInterface" / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.data_dir / "history.json"

        self.active_config: Dict[str, Any] = {}
        self.domain: Dict[str, Any] = {}
        self.engine = None
        self.telemetry_collector = None
        self._last_stalled = False
        self.target_time: float = 0.0
        self.running = False
        self.after_id: Optional[str] = None
        self.lift_drag_points: List[Tuple[float, float]] = []
        self.history = self._load_history()

        self.container = ctk.CTkFrame(self, fg_color="#0b1220")
        self.container.pack(fill="both", expand=True, padx=12, pady=12)


        self.db = SimulationDatabase()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.screens: Dict[str, ctk.CTkFrame] = {}
        self._build_screens()
        self.show_screen("menu")
    def _build_screens(self) -> None:
        self.screens["menu"] = MainMenuScreen(
            self.container,
            on_new=lambda: self.show_screen("config"),
            on_history=lambda: self.show_screen("history"),
            on_aircraft_spec=lambda: self.show_screen("aircraft_spec"),
            on_create_aircraft=lambda: self.show_screen("aircraft_builder"),
            db=self.db,
            history=self.history,
        )
        self.screens["aircraft_spec"] = AircraftSpecScreen(
            self.container,
            on_back=lambda: self.show_screen("menu"),
            db=self.db,
        )
        self.screens["aircraft_builder"] = AircraftBuilderScreen(
            self.container,
            on_back=lambda: self.show_screen("menu"),
            db=self.db,
            on_saved=self._on_aircraft_saved,
        )
        self.screens["config"] = ConfigScreen(
            self.container,
            on_run=self.start_simulation,
            on_menu=lambda: self.show_screen("menu"),
            db=self.db,
        )
        self.screens["live"] = LiveDashboardScreen(
            self.container,
            on_cancel=self.stop_simulation,
            on_pause=self.toggle_pause,
            on_export=self.export_current_log,
        )
        self.screens["summary"] = SummaryScreen(
            self.container,
            on_menu=lambda: self.show_screen("menu"),
            on_history=lambda: self.show_screen("history"),
        )
        self.screens["history"] = HistoryScreen(
            self.container,
            history=self.history,
            on_view=self._load_summary_from_history,
            on_reload=self._reload_config_from_history,
            on_delete=self._delete_history_entry,
            on_menu=lambda: self.show_screen("menu"),
        )

    def _on_aircraft_saved(self, aircraft_id: int) -> None:
        try:
            config_screen: ConfigScreen = self.screens["config"]  # type: ignore
            if hasattr(config_screen, "reload_aircraft_list"):
                config_screen.reload_aircraft_list()  # type: ignore[attr-defined]
            if hasattr(config_screen, "select_aircraft_id"):
                config_screen.select_aircraft_id(aircraft_id)  # type: ignore[attr-defined]
        except Exception:
            traceback.print_exc()
        self.show_screen("config")

    def on_closing(self):
        if hasattr(self, "db"):
            self.db.close()
        self.destroy()
        
    def show_screen(self, name: str) -> None:
        for child in self.container.winfo_children():
            child.pack_forget()
        screen = self.screens[name]
        if name == "menu" and hasattr(screen, "refresh_system_info"):
            try:
                screen.refresh_system_info(self.db, self.history)  # type: ignore[attr-defined]
            except Exception:
                traceback.print_exc()
        screen.pack(fill="both", expand=True)
        if name == "history":
            self.screens["history"].refresh(self.history)  # type: ignore
    def _load_history(self) -> List[Dict[str, Any]]:
        if not self.history_file.exists():
            return []
        try:
            return json.loads(self.history_file.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save_history(self) -> None:
        self.history_file.write_text(json.dumps(self.history, indent=2), encoding="utf-8")

    def _build_config(self) -> Tuple[Optional[Dict[str, Any]], List[str]]:
        config_screen: ConfigScreen = self.screens["config"]  # type: ignore
        return config_screen.build_config()
    def start_simulation(self) -> None:
        cfg, errors = self._build_config()
        if errors or cfg is None:
            self.screens["config"].show_errors(errors)  # type: ignore
            return
        if SimulationBuilder is None or SimulationRun is None:
            self.screens["config"].show_errors(["Simulation backend not available."])  # type: ignore
            return

        self.active_config = cfg
        self.target_time = cfg["timeEnd"]
        self.running = False
        self.lift_drag_points = []

        # Save to database
        if self.db.conn:
            try:
                sim_id = self.db.saveSim(cfg)
                if sim_id is not None:
                    cfg["simId"] = sim_id
            except Exception as exc:
                traceback.print_exc()
                self.screens["config"].show_errors([str(exc)])  # type: ignore
                return

        try:
            self.domain = SimulationBuilder.build(self.active_config)
            self.engine = SimulationRun.create(
                self.active_config,
                self.domain["controls"],
                self.domain["integrator"],
                self.domain.get("sensors"),
                self.domain.get("kalman"),
                self.domain.get("stall"),
            )
        except Exception as exc:
            traceback.print_exc()
            self.screens["config"].show_errors([f"Failed to prepare simulation: {exc}"])  # type: ignore
            return

        live_screen: LiveDashboardScreen = self.screens["live"]  # type: ignore
        self.telemetry_collector = None
        if TelemetryCollector is not None:
            self.telemetry_collector = TelemetryCollector(self.domain, self.active_config)
        self._last_stalled = False
        live_screen.reset_dashboard(self.active_config)
        self.show_screen("live")
        self.running = True
        self._step_loop()
    def _step_loop(self) -> None:
        if not self.running or self.engine is None:
            return
        try:
            self.engine.step()
        except Exception as exc:
            traceback.print_exc()
            self._handle_runtime_error(f"Simulation crashed: {exc}")
            return

        ctx = self.engine.ctx
        live_screen: LiveDashboardScreen = self.screens["live"]  # type: ignore

        snap = None
        if self.telemetry_collector is not None:
            try:
                snap = self.telemetry_collector.collect(ctx)
            except Exception:
                traceback.print_exc()
                snap = None

        if snap is not None:
            live_screen.update_snapshot(snap)
            if bool(snap.stalled) and not self._last_stalled:
                live_screen.log_event(f"STALL detected at t={snap.t:.2f}s")
            self._last_stalled = bool(snap.stalled)

        state = np.array(ctx.trueState).flatten()
        if self._has_numeric_failure(ctx, state):
            return

        if ctx.t >= self.target_time:
            self._finish_run(success=True)
            return

        self.after_id = self.after(40, self._step_loop)

    def toggle_pause(self) -> None:
        if self.engine is None:
            return
        if self.running:
            self.running = False
            if self.after_id:
                self.after_cancel(self.after_id)
                self.after_id = None
            self.screens["live"].log_event("Paused")  # type: ignore
        else:
            self.running = True
            self.screens["live"].log_event("Resumed")  # type: ignore
            self._step_loop()

    def export_current_log(self) -> None:
        if self.engine is None or not hasattr(self.engine, "log"):
            return
        uid = self.active_config.get("uid", "SIM")
        csv_path = self.data_dir / f"{uid}_export.csv"
        try:
            with csv_path.open("w", encoding="utf-8") as f:
                f.write("Time,u,w,q,theta,x,z,elevator,thrust,stall\n")
                for row in self.engine.log:
                    state = np.array(row.get("True State") if row.get("True State") is not None else []).flatten()
                    vals = [row.get("Time", 0.0)]
                    vals.extend([state[i] if i < state.size else "" for i in range(6)])
                    vals.append(row.get("Elevator", ""))
                    vals.append(row.get("Thrust", ""))
                    vals.append(row.get("Stall", ""))
                    f.write(",".join(map(str, vals)) + "\n")
            self.screens["live"].log_event(f"Exported log to {csv_path.name}")  # type: ignore
        except Exception:
            traceback.print_exc()

    def _estimate_lift_drag(self, state: np.ndarray) -> Tuple[float, float]:
        lift = 0.0
        drag = 0.0

        if "forces" in self.domain and "environment" in self.domain:
            u = float(state[0]) if state.size > 0 else 0.0
            w = float(state[1]) if state.size > 1 else 0.0
            theta = float(state[3]) if state.size > 3 else 0.0
            z = float(state[5]) if state.size > 5 else 0.0
            
            v_res = math.sqrt(u * u + w * w)
            gamma = math.atan2(w, u) if v_res > 1e-9 else 0.0
            aoa = theta - gamma
            
            density = 1.225
            env = self.domain["environment"]
            if hasattr(env, "density"):
                density = float(env.density(z))

            lift, drag, _ = self.domain["forces"].aeroForces(density, v_res, aoa, True)

        return float(lift), float(drag)

    def _has_numeric_failure(self, ctx: Any, state: np.ndarray) -> bool:
        if np.isnan(state).any():
            self._handle_runtime_error(f"Simulation terminated due to numerical error at time = {ctx.t:.2f}")
            return True
        if np.linalg.norm(state) > 1e6:
            self._handle_runtime_error(f"Simulation terminated due to divergence at time = {ctx.t:.2f}")
            return True
        return False

    def _handle_runtime_error(self, message: str) -> None:
        self.running = False
        live_screen: LiveDashboardScreen = self.screens["live"]  # type: ignore
        live_screen.show_error(message)
        self._finish_run(success=False, failure_message=message)

    def stop_simulation(self) -> None:
        self.running = False
        if self.after_id:
            self.after_cancel(self.after_id)
        self.show_screen("config")
    def _finish_run(self, success: bool, failure_message: Optional[str] = None) -> None:
        self.running = False
        if self.after_id:
            self.after_cancel(self.after_id)

        if self.engine is None:
            return

        summary = self._build_summary(self.engine.log, success, failure_message)
        summary_screen: SummaryScreen = self.screens["summary"]  # type: ignore
        summary_screen.show_summary(summary, self.active_config)
        self._persist_run(summary)
        uid = self.active_config.get("uid", "SIM")
        summary_screen.set_event_index_paths(
            str(self.data_dir / f"{uid}.csv"),
            str(self.data_dir / f"{uid}_index.csv"),
        )
        self.show_screen("summary")

    def _build_summary(self, log: List[Dict[str, Any]], success: bool, failure_message: Optional[str]) -> Dict[str, Any]:
        max_airspeed = 0.0
        max_ld = 0.0
        max_pitch_rate = 0.0
        duration = self.target_time
        for idx, row in enumerate(log):
            state = row.get("True State")
            if state is None:
                continue
            arr = np.array(state).flatten()
            if arr.size >= 2:
                max_airspeed = max(max_airspeed, float(np.linalg.norm(arr[:2])))
            if arr.size >= 3:
                max_pitch_rate = max(max_pitch_rate, abs(float(arr[2])))
            if idx < len(self.lift_drag_points):
                lift, drag = self.lift_drag_points[idx]
                if drag != 0:
                    max_ld = max(max_ld, abs(lift / drag))

        return {
            "time": _now_str(),
            "success": success,
            "message": failure_message or "Simulation completed",
            "duration": duration,
            "maxAirspeed": max_airspeed,
            "maxLiftToDrag": max_ld,
            "maxPitchRate": max_pitch_rate,
            "trimResult": self.active_config.get("trimSolver", {}).get("toleration", "n/a"),
        }

    def _persist_run(self, summary: Dict[str, Any]) -> None:
        uid = self.active_config.get("uid", "SIM")
        csv_path = self.data_dir / f"{uid}.csv"
        if self.engine and hasattr(self.engine, "log"):
            try:
                with csv_path.open("w", encoding="utf-8") as f:
                    f.write("Time,u,w,q,theta,x,z,elevator,thrust,stall\n")
                    for row in self.engine.log:
                        state = np.array(row.get("True State") if row.get("True State") is not None else []).flatten()
                        vals = [row.get("Time", 0.0)]
                        vals.extend([state[i] if i < state.size else "" for i in range(6)])
                        vals.append(row.get("Elevator", ""))
                        vals.append(row.get("Thrust", ""))
                        vals.append(row.get("Stall", ""))
                        f.write(",".join(map(str, vals)) + "\n")
            except Exception:
                pass

        index_path = self.data_dir / f"{uid}_index.csv"
        try:
            segment_seconds = float(self.active_config.get("dataOutput", {}).get("segmentSeconds", 1.0))
        except Exception:
            segment_seconds = 1.0

        if SegmentIndexer is not None and bool(self.active_config.get("dataOutput", {}).get("recordRaw", True)):
            try:
                SegmentIndexer(segment_seconds=segment_seconds).build_index(csv_path, index_path)
            except Exception:
                traceback.print_exc()

        entry = {
            "uid": uid,
            "name": self.active_config.get("name", "Simulation"),
            "created": self.active_config.get("createdAt", _now_str()),
            "aircraft": self.active_config.get("aircraftType"),
            "duration": summary["duration"],
            "maxAirspeed": summary["maxAirspeed"],
            "maxLiftToDrag": summary["maxLiftToDrag"],
            "maxPitchRate": summary["maxPitchRate"],
            "trimResult": summary["trimResult"],
            "success": summary["success"],
            "message": summary["message"],
            "config": self.active_config,
            "logPath": str(csv_path),
            "indexPath": str(index_path) if index_path.exists() else "",
        }
        self.history.insert(0, entry)
        self._save_history()

    def _load_summary_from_history(self, item: Dict[str, Any]) -> None:
        summary_screen: SummaryScreen = self.screens["summary"]  # type: ignore
        summary = {
            "time": item.get("created", ""),
            "success": item.get("success", False),
            "message": item.get("message", ""),
            "duration": item.get("duration", 0.0),
            "maxAirspeed": item.get("maxAirspeed", 0.0),
            "maxLiftToDrag": item.get("maxLiftToDrag", 0.0),
            "maxPitchRate": item.get("maxPitchRate", 0.0),
            "trimResult": item.get("trimResult", "n/a"),
        }
        summary_screen.show_summary(summary, item.get("config", {}))
        summary_screen.set_event_index_paths(item.get("logPath"), item.get("indexPath"))
        self.show_screen("summary")

    def _reload_config_from_history(self, item: Dict[str, Any]) -> None:
        cfg = item.get("config")
        if not cfg:
            return
        config_screen: ConfigScreen = self.screens["config"]  # type: ignore
        config_screen.load_config(cfg)
        self.show_screen("config")

    def _delete_history_entry(self, item: Dict[str, Any]) -> None:
        self.history = [h for h in self.history if h.get("uid") != item.get("uid")]
        self._save_history()
        self.screens["history"].refresh(self.history)  # type: ignore
class MainMenuScreen(ctk.CTkFrame):
    def __init__(
        self,
        parent: ctk.CTkFrame,
        on_new,
        on_history,
        on_aircraft_spec,
        on_create_aircraft=None,
        db: Optional[SimulationDatabase] = None,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        super().__init__(parent, fg_color="#0b1220")
        self._db = db
        self._history = history or []
        self.on_new = on_new
        self.on_history = on_history
        self.on_aircraft_spec = on_aircraft_spec
        self.on_create_aircraft = on_create_aircraft

        # Title section
        title = ctk.CTkFrame(self, fg_color="#0b1220")
        title.pack(fill="x", pady=(28, 14))

        title_row = ctk.CTkFrame(title, fg_color="transparent")
        title_row.pack()

        ctk.CTkLabel(title_row, text="Flight Data Simulator", font=ctk.CTkFont(size=30, weight="bold")).pack(
            side="left", padx=(0, 10)
        )

        # Static Cessna-style silhouette (no animation).
        self.plane_canvas = tk.Canvas(title_row, width=160, height=54, bg="#0b1220", highlightthickness=0)
        self.plane_canvas.pack(side="left")
        # Wings
        self.plane_canvas.create_polygon(28, 25, 132, 25, 132, 33, 28, 33, fill="#60a5fa", outline="#93c5fd", width=1)
        # Tailplane
        self.plane_canvas.create_polygon(60, 40, 100, 40, 100, 46, 60, 46, fill="#60a5fa", outline="#93c5fd", width=1)
        # Fuselage
        self.plane_canvas.create_polygon(73, 10, 87, 10, 90, 44, 70, 44, fill="#3b82f6", outline="#93c5fd", width=1)
        # Nose
        self.plane_canvas.create_polygon(73, 10, 80, 2, 87, 10, fill="#3b82f6", outline="#93c5fd", width=1)
        # Vertical tail
        self.plane_canvas.create_polygon(77, 32, 83, 32, 83, 52, 77, 52, fill="#3b82f6", outline="#93c5fd", width=1)

        ctk.CTkLabel(title, text="By Hemang Khandelwal", text_color="#9ca3af").pack(pady=(6, 4))
        ctk.CTkLabel(
            title,
            text="Simulate and analyse aircraft flight dynamics",
            text_color="#cbd5e1",
        ).pack()

        # Main content
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=18, pady=(0, 12))

        left = ctk.CTkFrame(body, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))

        right = ctk.CTkFrame(body, fg_color="#0f172a", corner_radius=12)
        right.pack(side="right", fill="y", padx=(10, 0))

        # Buttons panel
        btn_panel = ctk.CTkFrame(left, fg_color="#0f172a", corner_radius=12)
        btn_panel.pack(fill="x", padx=6, pady=(0, 10))
        ctk.CTkLabel(btn_panel, text="Start", font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", padx=14, pady=(12, 8)
        )

        ctk.CTkButton(
            btn_panel,
            text="New Simulation",
            height=56,
            command=self.on_new,
            fg_color="#10b981",
            hover_color="#34d399",
            text_color="black",
        ).pack(padx=14, pady=(0, 10), fill="x")

        ctk.CTkButton(
            btn_panel,
            text="View Previous Simulations",
            height=46,
            command=self.on_history,
            fg_color="#111827",
            hover_color="#1f2937",
        ).pack(padx=14, pady=6, fill="x")

        ctk.CTkButton(
            btn_panel,
            text="Aircraft Specification",
            height=46,
            command=self.on_aircraft_spec,
            fg_color="#111827",
            hover_color="#1f2937",
        ).pack(padx=14, pady=(6, 14), fill="x")

        ctk.CTkButton(
            btn_panel,
            text="Create Custom Aircraft",
            height=40,
            command=(self.on_create_aircraft or (lambda: None)),
            fg_color="#1d4ed8",
            hover_color="#2563eb",
        ).pack(padx=14, pady=(0, 14), fill="x")

        # Recent simulations preview (simple)
        recent = ctk.CTkFrame(left, fg_color="#0f172a", corner_radius=12)
        recent.pack(fill="x", padx=6, pady=(0, 10))
        ctk.CTkLabel(recent, text="Recent Simulations", font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", padx=14, pady=(12, 8)
        )
        self.recent_lines: List[ctk.CTkLabel] = []
        for _ in range(3):
            lbl = ctk.CTkLabel(recent, text="", text_color="#cbd5e1")
            lbl.pack(anchor="w", padx=14, pady=2)
            self.recent_lines.append(lbl)
        ctk.CTkLabel(recent, text="(Preview only)", text_color="#64748b").pack(anchor="w", padx=14, pady=(6, 12))

        # System info (labels only; minimal logic)
        ctk.CTkLabel(right, text="System Info", font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", padx=14, pady=(12, 8)
        )
        self.db_status_label = ctk.CTkLabel(right, text="", text_color="#cbd5e1")
        self.db_status_label.pack(anchor="w", padx=14, pady=2)
        self.saved_count_label = ctk.CTkLabel(right, text="", text_color="#cbd5e1")
        self.saved_count_label.pack(anchor="w", padx=14, pady=2)
        self.last_run_label = ctk.CTkLabel(right, text="", text_color="#cbd5e1", wraplength=260, justify="left")
        self.last_run_label.pack(anchor="w", padx=14, pady=(2, 12))

        # Footer
        ctk.CTkLabel(self, text="v1.0 – RK4 Simulation Model", text_color="#64748b").pack(
            side="bottom", pady=(0, 10)
        )

        self.refresh_system_info(self._db, self._history)

    def refresh_system_info(self, db: Optional[SimulationDatabase], history: List[Dict[str, Any]]) -> None:
        self._db = db
        self._history = history or []

        connected = bool(getattr(self._db, "conn", None))
        self.db_status_label.configure(
            text=f"Database: {'Connected' if connected else 'Not connected'}",
            text_color="#22c55e" if connected else "#f97316",
        )

        # Simple placeholders driven by in-memory history (no DB queries yet).
        self.saved_count_label.configure(text=f"Saved simulations: {len(self._history)}")

        last = "Last run: (none yet)"
        if self._history:
            h0 = self._history[0]
            last = f"Last run: {h0.get('uid', 'SIM')} – {('Completed' if h0.get('success', False) else 'Failed')}"
        self.last_run_label.configure(text=last)

        preview: List[str] = []
        if self._history:
            for h in self._history[:3]:
                status = "Completed" if h.get("success", False) else "Failed"
                preview.append(f"{h.get('uid', 'SIM')} – {status}")
        if not preview:
            preview = ["Sim_01 – Completed", "Sim_02 – Stall detected", "Sim_03 – Completed"]

        for i, lbl in enumerate(self.recent_lines):
            lbl.configure(text=preview[i] if i < len(preview) else "")

class AircraftBuilderScreen(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame, on_back, db: SimulationDatabase, on_saved) -> None:
        super().__init__(parent, fg_color="#0b1220")
        self.on_back = on_back
        self.db = db
        self.on_saved = on_saved

        self.fields: Dict[str, ctk.CTkEntry] = {}
        self.status = ctk.CTkLabel(self, text="", text_color="#ef4444")

        header = ctk.CTkFrame(self, fg_color="#0b1220")
        header.pack(fill="x", pady=(4, 10))
        ctk.CTkButton(header, text="Back to Menu", width=140, command=self.on_back).pack(side="left", padx=4)
        ctk.CTkLabel(header, text="Create Custom Aircraft", font=ctk.CTkFont(size=20, weight="bold")).pack(
            side="left", padx=8
        )
        ctk.CTkButton(header, text="Save Aircraft", width=160, fg_color="#10b981", command=self._save).pack(
            side="right", padx=4
        )

        self.status.pack(fill="x", padx=10, pady=(0, 8))

        self.tabs = ctk.CTkTabview(self, fg_color="#0f172a", corner_radius=12)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_form()

    def _tab_scroll(self, tab_name: str) -> ctk.CTkScrollableFrame:
        tab = self.tabs.add(tab_name)
        frame = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        return frame

    def _entry(self, parent, key: str, label: str, default: str = "", width: int = 220) -> ctk.CTkEntry:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=4)
        ctk.CTkLabel(row, text=label, text_color="#cbd5e1").pack(side="left", padx=(4, 10))
        entry = ctk.CTkEntry(row, width=width)
        entry.insert(0, default)
        entry.pack(side="left")
        self.fields[key] = entry
        return entry

    def _build_form(self) -> None:
        aircraft = self._tab_scroll("Aircraft")
        self._entry(aircraft, "aircraft_name", "Name", "Falcon LSA-100")
        self._entry(aircraft, "aircraft_manufacturer", "Manufacturer", "FalconWorks")

        airfoil = self._tab_scroll("AirfoilData")
        self._entry(airfoil, "WingArea", "WingArea (m^2)", "10.8")
        self._entry(airfoil, "AerodynamicChord", "AerodynamicChord (m)", "1.10")
        self._entry(airfoil, "WingAirfoil", "WingAirfoil (e.g. NACA 2412)", "NACA 4415")
        self._entry(airfoil, "HorizontalAirfoilAtRoot", "HorizontalAirfoilAtRoot", "NACA 0012")
        self._entry(airfoil, "HorizontalAirfoilAtTip", "HorizontalAirfoilAtTip", "NACA 0010")
        self._entry(airfoil, "AileronsDeflectionLimit", "AileronsDeflectionLimit (deg)", "20")
        self._entry(airfoil, "AileronsArea", "AileronsArea (m^2)", "0.85")
        self._entry(airfoil, "ElevatorDeflectionLimitMax", "ElevatorDeflectionLimitMax (deg)", "25")
        self._entry(airfoil, "ElevatorDeflectionLimitMin", "ElevatorDeflectionLimitMin (deg)", "-20")
        self._entry(airfoil, "ElevatorArea", "ElevatorArea (m^2)", "0.55")
        self._entry(airfoil, "RudderDeflectionLimit", "RudderDeflectionLimit (deg)", "25")
        self._entry(airfoil, "FlapsArea", "FlapsArea (m^2)", "1.10")
        self._entry(airfoil, "FlapsDeflectionLimit", "FlapsDeflectionLimit (deg)", "30")

        engine = self._tab_scroll("EngineData")
        self._entry(engine, "ModelName", "ModelName", "FW-100i")
        self._entry(engine, "RatedPower", "RatedPower (kW)", "75")
        self._entry(engine, "Displacement", "Displacement (cc)", "1350")
        self._entry(engine, "Height", "Engine Height (m)", "0.60")
        self._entry(engine, "Width", "Engine Width (m)", "0.65")
        self._entry(engine, "Length", "Engine Length (m)", "0.80")
        self._entry(engine, "SpecificFuelConsumption", "SpecificFuelConsumption (kg/kW/h)", "0.30")
        self._entry(engine, "NoOfBlades", "NoOfBlades (int)", "2")
        self._entry(engine, "PropellerDiameter", "PropellerDiameter (m)", "1.78")

        perf = self._tab_scroll("PerformanceData")
        self._entry(perf, "NormalMaxTakeOffWeight", "NormalMaxTakeOffWeight (kg)", "600")
        self._entry(perf, "UtilityMaxTakeOffWeight", "UtilityMaxTakeOffWeight (kg)", "560")
        self._entry(perf, "StallSpeed", "StallSpeed (knots)", "39")
        self._entry(perf, "CruiseSpeed", "CruiseSpeed (knots)", "105")
        self._entry(perf, "SeaLevelMaxSpeed", "SeaLevelMaxSpeed (knots)", "120")
        self._entry(perf, "NeverExceedSpeed", "NeverExceedSpeed (knots)", "145")
        self._entry(perf, "ServiceCeiling", "ServiceCeiling (ft)", "14000")
        self._entry(perf, "TakeOffRun", "TakeOffRun (m)", "290")
        self._entry(perf, "LandingRun", "LandingRun (m)", "310")
        self._entry(perf, "EightyRange", "EightyRange (nm)", "520")
        self._entry(perf, "SixtyRange", "SixtyRange (nm)", "650")

        geo = self._tab_scroll("Geometry")
        self._entry(geo, "GeoLength", "Length (m)", "6.20")
        self._entry(geo, "GeoHeight", "Height (m)", "2.10")
        self._entry(geo, "WheelBase", "WheelBase (m)", "1.65")
        self._entry(geo, "WheelTrack", "WheelTrack (m)", "2.20")

    def _get_text(self, key: str) -> str:
        val = self.fields[key].get().strip()
        if val == "":
            raise ValueError(f"{key} is required")
        return val

    def _get_float(self, key: str) -> float:
        raw = self.fields[key].get().strip()
        if raw == "":
            raise ValueError(f"{key} is required")
        try:
            return float(raw)
        except Exception:
            raise ValueError(f"{key} must be a number")

    def _get_int(self, key: str) -> int:
        raw = self.fields[key].get().strip()
        if raw == "":
            raise ValueError(f"{key} is required")
        try:
            return int(float(raw))
        except Exception:
            raise ValueError(f"{key} must be an integer")

    def _save(self) -> None:
        self.status.configure(text="", text_color="#ef4444")
        if not getattr(self.db, "conn", None):
            self.status.configure(text="Database not connected.", text_color="#ef4444")
            return

        try:
            aircraft = {
                "Name": self._get_text("aircraft_name"),
                "Manufacturer": self.fields["aircraft_manufacturer"].get().strip(),
            }
            airfoil = {
                "WingArea": self._get_float("WingArea"),
                "AerodynamicChord": self._get_float("AerodynamicChord"),
                "WingAirfoil": self._get_text("WingAirfoil"),
                "HorizontalAirfoilAtRoot": self._get_text("HorizontalAirfoilAtRoot"),
                "HorizontalAirfoilAtTip": self._get_text("HorizontalAirfoilAtTip"),
                "AileronsDeflectionLimit": self._get_float("AileronsDeflectionLimit"),
                "AileronsArea": self._get_float("AileronsArea"),
                "ElevatorDeflectionLimitMax": self._get_float("ElevatorDeflectionLimitMax"),
                "ElevatorDeflectionLimitMin": self._get_float("ElevatorDeflectionLimitMin"),
                "ElevatorArea": self._get_float("ElevatorArea"),
                "RudderDeflectionLimit": self._get_float("RudderDeflectionLimit"),
                "FlapsArea": self._get_float("FlapsArea"),
                "FlapsDeflectionLimit": self._get_float("FlapsDeflectionLimit"),
            }
            engine = {
                "ModelName": self._get_text("ModelName"),
                "RatedPower": self._get_float("RatedPower"),
                "Displacement": self._get_float("Displacement"),
                "Height": self._get_float("Height"),
                "Width": self._get_float("Width"),
                "Length": self._get_float("Length"),
                "SpecificFuelConsumption": self._get_float("SpecificFuelConsumption"),
                "NoOfBlades": self._get_int("NoOfBlades"),
                "PropellerDiameter": self._get_float("PropellerDiameter"),
            }
            performance = {
                "NormalMaxTakeOffWeight": self._get_float("NormalMaxTakeOffWeight"),
                "UtilityMaxTakeOffWeight": self._get_float("UtilityMaxTakeOffWeight"),
                "StallSpeed": self._get_float("StallSpeed"),
                "CruiseSpeed": self._get_float("CruiseSpeed"),
                "SeaLevelMaxSpeed": self._get_float("SeaLevelMaxSpeed"),
                "NeverExceedSpeed": self._get_float("NeverExceedSpeed"),
                "ServiceCeiling": self._get_float("ServiceCeiling"),
                "TakeOffRun": self._get_float("TakeOffRun"),
                "LandingRun": self._get_float("LandingRun"),
                "EightyRange": self._get_float("EightyRange"),
                "SixtyRange": self._get_float("SixtyRange"),
            }
            geometry = {
                "Length": self._get_float("GeoLength"),
                "Height": self._get_float("GeoHeight"),
                "WheelBase": self._get_float("WheelBase"),
                "WheelTrack": self._get_float("WheelTrack"),
            }

            aircraft_id = self.db.create_custom_aircraft(aircraft, airfoil, engine, performance, geometry)
            if aircraft_id is None:
                self.status.configure(text="Save failed (no AircraftID returned).", text_color="#ef4444")
                return

            self.status.configure(text=f"Saved: AircraftID {aircraft_id}", text_color="#22c55e")
            try:
                self.on_saved(int(aircraft_id))
            except Exception:
                traceback.print_exc()
        except Exception as exc:
            self.status.configure(text=str(exc), text_color="#ef4444")

class AircraftSpecScreen(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame, on_back, db: SimulationDatabase):
        super().__init__(parent, fg_color="#0b1220")
        self.db = db
        self.error_label = ctk.CTkLabel(self, text="", text_color="red")
        self.current_aircraft_id: Optional[int] = None

        header = ctk.CTkFrame(self, fg_color="#0b1220")
        header.pack(fill="x", pady=(10, 6))
        ctk.CTkButton(header, text="Back to Menu", width=120, command=on_back).pack(side="left", padx=8)
        ctk.CTkLabel(header, text="Aircraft Specifications", font=ctk.CTkFont(size=22, weight="bold")).pack(
            side="left", padx=8
        )

        self.error_label.pack(fill="x", padx=12, pady=(0, 6))

        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.pack(fill="x", padx=12, pady=(0, 8))
        self.aircraft_choice = ctk.CTkComboBox(controls, values=self._get_aircraft_list(), width=360)
        self.aircraft_choice.pack(side="left")
        ctk.CTkButton(
            controls,
            text="Load Details",
            command=self.load_aircraft_details,
            fg_color="#10b981",
            width=140,
        ).pack(side="left", padx=10)

        # Highlight cards (big, quick-glance)
        self.hero = ctk.CTkFrame(self, fg_color="#0f172a", corner_radius=14)
        self.hero.pack(fill="x", padx=12, pady=(0, 10))
        self.hero_title = ctk.CTkLabel(
            self.hero,
            text="Select an aircraft to view specs",
            font=ctk.CTkFont(size=18, weight="bold"),
        )
        self.hero_title.pack(anchor="w", padx=14, pady=(12, 2))
        self.hero_sub = ctk.CTkLabel(self.hero, text="Engine, airfoil, performance, geometry", text_color="#9ca3af")
        self.hero_sub.pack(anchor="w", padx=14, pady=(0, 10))
        self.hero_cards = ctk.CTkFrame(self.hero, fg_color="transparent")
        self.hero_cards.pack(fill="x", padx=10, pady=(0, 12))

        self._hero_card_widgets: Dict[str, ctk.CTkLabel] = {}
        for title, key, color in [
            ("Cruise", "cruise", "#22c55e"),
            ("Stall", "stall", "#f97316"),
            ("Power", "power", "#3b82f6"),
            ("Wing Area", "wing_area", "#a855f7"),
        ]:
            card = ctk.CTkFrame(self.hero_cards, fg_color="#111827", corner_radius=14)
            card.pack(side="left", expand=True, fill="x", padx=6)
            badge = tk.Canvas(card, width=44, height=44, bg="#111827", highlightthickness=0)
            badge.pack(side="left", padx=(12, 10), pady=12)
            badge.create_oval(6, 6, 38, 38, fill=color, outline=color)
            text = ctk.CTkFrame(card, fg_color="transparent")
            text.pack(side="left", fill="both", expand=True, pady=12)
            ctk.CTkLabel(text, text=title, text_color="#9ca3af").pack(anchor="w")
            value_label = ctk.CTkLabel(text, text="N/A", font=ctk.CTkFont(size=16, weight="bold"))
            value_label.pack(anchor="w")
            self._hero_card_widgets[key] = value_label

        # Category tabs (pages)
        self.tabs = ctk.CTkTabview(self, fg_color="#0f172a", corner_radius=12)
        self.tabs.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.tab_frames: Dict[str, ctk.CTkScrollableFrame] = {}
        for name in ["Engine", "Airfoil", "Performance", "Geometry"]:
            tab = self.tabs.add(name)
            frame = ctk.CTkScrollableFrame(tab, fg_color="transparent")
            frame.pack(fill="both", expand=True, padx=8, pady=8)
            self.tab_frames[name] = frame

    def _get_aircraft_list(self):
        if not self.db.conn:
            return ["1 - Cessna 172", "2 - Piper"]

        cursor = self.db.conn.cursor()
        try:
            for label_col in ["Name", "AircraftType"]:
                try:
                    cursor.execute(f"SELECT AircraftID, {label_col} FROM Aircraft")
                    rows = cursor.fetchall()
                    if rows:
                        return [f"{r[0]} - {r[1]}" for r in rows]
                except Exception:
                    continue
        except Exception:
            pass
        return ["1 - Cessna 172", "2 - Piper"]

    def _clear_specs(self):
        for frame in self.tab_frames.values():
            for child in frame.winfo_children():
                child.destroy()

    def _add_spec_card(self, parent: ctk.CTkScrollableFrame, title: str, value: Any, accent: str):
        card = ctk.CTkFrame(parent, fg_color="#111827", corner_radius=12)
        card.pack(fill="x", padx=6, pady=6)

        left = ctk.CTkFrame(card, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=12, pady=10)
        ctk.CTkLabel(left, text=title, text_color="#9ca3af").pack(anchor="w")
        v = "N/A" if value is None else str(value)
        ctk.CTkLabel(left, text=v, font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w")

        badge = tk.Canvas(card, width=20, height=52, bg="#111827", highlightthickness=0)
        badge.pack(side="right", padx=10, pady=10)
        badge.create_rectangle(6, 6, 14, 46, fill=accent, outline=accent)

    def load_aircraft_details(self):
        self.error_label.configure(text="")
        raw = self.aircraft_choice.get()
        if not raw:
            return
        aircraft_id = int(raw.split("-")[0].strip())
        self.current_aircraft_id = aircraft_id

        aircraft_data = AircraftData.from_aircraft_id(aircraft_id)

        engine_specs = [
            ("Engine Model", aircraft_data.modelName(), "#3b82f6"),
            ("Rated Power (kW)", aircraft_data.ratedPower(), "#3b82f6"),
            ("Displacement", aircraft_data.displacement(), "#3b82f6"),
            ("Engine Height", aircraft_data.engineHeight(), "#3b82f6"),
            ("Engine Width", aircraft_data.engineWidth(), "#3b82f6"),
            ("Engine Length", aircraft_data.engineLength(), "#3b82f6"),
            ("Specific Fuel Consumption", aircraft_data.specificFuelConsumption(), "#3b82f6"),
            ("No. of Blades", aircraft_data.noOfBlades(), "#3b82f6"),
            ("Propeller Diameter", aircraft_data.propellerDiameter(), "#3b82f6"),
        ]

        airfoil_specs = [
            ("Wing Area", aircraft_data.wingArea(), "#a855f7"),
            ("Aerodynamic Chord", aircraft_data.aerodynamicChord(), "#a855f7"),
            ("Wing Airfoil", aircraft_data.wingAirfoil(), "#a855f7"),
            ("Horizontal Airfoil Root", aircraft_data.horizontalAirfoilAtRoot(), "#a855f7"),
            ("Horizontal Airfoil Tip", aircraft_data.horizontalAirfoilAtTip(), "#a855f7"),
            ("Ailerons Deflection Limit", aircraft_data.aileronsDeflectionLimit(), "#a855f7"),
            ("Ailerons Area", aircraft_data.aileronsArea(), "#a855f7"),
            ("Elevator Deflection Limit Max", aircraft_data.elevatorDeflectionLimitMax(), "#a855f7"),
            ("Elevator Deflection Limit Min", aircraft_data.elevatorDeflectionLimitMin(), "#a855f7"),
            ("Elevator Area", aircraft_data.elevatorArea(), "#a855f7"),
            ("Rudder Deflection Limit", aircraft_data.rudderDeflectionLimit(), "#a855f7"),
            ("Flaps Area", aircraft_data.flapsArea(), "#a855f7"),
            ("Flaps Deflection Limit", aircraft_data.flapsDeflectionLimit(), "#a855f7"),
        ]

        performance_specs = [
            ("Normal Max TakeOff Weight", aircraft_data.normalMaxTakeOffWeight(), "#22c55e"),
            ("Utility Max TakeOff Weight", aircraft_data.utilityMaxTakeOffWeight(), "#22c55e"),
            ("Stall Speed", aircraft_data.stallSpeed(), "#f97316"),
            ("Cruise Speed", aircraft_data.cruiseSpeed(), "#22c55e"),
            ("Sea Level Max Speed", aircraft_data.seaLevelMaxSpeed(), "#22c55e"),
            ("Never Exceed Speed", aircraft_data.neverExceedSpeed(), "#ef4444"),
            ("Service Ceiling", aircraft_data.serviceCeiling(), "#22c55e"),
            ("Take Off Run", aircraft_data.takeOffRun(), "#22c55e"),
            ("Landing Run", aircraft_data.landingRun(), "#22c55e"),
            ("Eighty Range", aircraft_data.eightyRange(), "#22c55e"),
            ("Sixty Range", aircraft_data.sixtyRange(), "#22c55e"),
        ]

        geometry_specs = [
            ("Length", aircraft_data.length(), "#fbbf24"),
            ("Height", aircraft_data.height(), "#fbbf24"),
            ("Wheel Base", aircraft_data.wheelBase(), "#fbbf24"),
            ("Wheel Track", aircraft_data.wheelTrack(), "#fbbf24"),
        ]

        self._clear_specs()
        for title, value, accent in engine_specs:
            self._add_spec_card(self.tab_frames["Engine"], title, value, accent)
        for title, value, accent in airfoil_specs:
            self._add_spec_card(self.tab_frames["Airfoil"], title, value, accent)
        for title, value, accent in performance_specs:
            self._add_spec_card(self.tab_frames["Performance"], title, value, accent)
        for title, value, accent in geometry_specs:
            self._add_spec_card(self.tab_frames["Geometry"], title, value, accent)

        def _set_hero(key: str, value: Any):
            lbl = self._hero_card_widgets.get(key)
            if lbl is None:
                return
            lbl.configure(text="N/A" if value is None else str(value))

        self.hero_title.configure(text=f"Aircraft ID {aircraft_id} specs")
        self.hero_sub.configure(text="Use tabs to view all categories")
        _set_hero("cruise", aircraft_data.cruiseSpeed())
        _set_hero("stall", aircraft_data.stallSpeed())
        _set_hero("power", aircraft_data.ratedPower())
        _set_hero("wing_area", aircraft_data.wingArea())

class ConfigScreen(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame, on_run, on_menu, db: Optional[SimulationDatabase] = None) -> None:
        super().__init__(parent, fg_color="#0b1220")
        self.on_run = on_run
        self.db = db
        self.error_label = ctk.CTkLabel(self, text="", text_color="red")

        self.fields: Dict[str, Any] = {}
        self.aircraft_choice: Optional[ctk.CTkComboBox] = None
        self._aircraft_labels: List[str] = []

        header = ctk.CTkFrame(self, fg_color="#0b1220")
        header.pack(fill="x", pady=(4, 10))
        ctk.CTkButton(header, text="Back to Menu", width=140, command=on_menu).pack(side="left", padx=4)
        ctk.CTkLabel(header, text="New Simulation Configuration", font=ctk.CTkFont(size=20, weight="bold")).pack(
            side="left", padx=8
        )
        ctk.CTkButton(header, text="Validate & Run", width=160, fg_color="#10b981", command=self.on_run).pack(
            side="right", padx=4
        )
        self.error_label.pack(fill="x")

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="#0f172a")
        self.scroll.pack(fill="both", expand=True, padx=6, pady=6)

        self._build_sections()
        self.load_defaults()

    def _section(self, title: str) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.scroll, fg_color="#111827", corner_radius=10)
        frame.pack(fill="x", padx=6, pady=6)
        ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=8, pady=6)
        return frame

    def _entry(self, parent, key: str, label: str, default: str = "", width: int = 140, state="normal"):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(row, text=label).pack(side="left", padx=4)
        entry = ctk.CTkEntry(row, width=width, state=state)
        entry.insert(0, default)
        entry.pack(side="left", padx=4)
        self.fields[key] = entry
        return entry

    def _get_aircraft_labels(self) -> List[str]:
        if self.db is None:
            return []
        try:
            aircraft = self.db.list_aircraft()
            return [f"{aid} - {name}" for aid, name in aircraft]
        except Exception:
            return []

    @staticmethod
    def _parse_aircraft_label(label: str) -> Tuple[Optional[int], str]:
        if not isinstance(label, str) or label.strip() == "":
            return (None, "")
        parts = label.split("-", 1)
        try:
            aid = int(parts[0].strip())
        except Exception:
            aid = None
        name = parts[1].strip() if len(parts) > 1 else label.strip()
        return (aid, name)

    def _find_aircraft_label_by_id(self, aircraft_id: int) -> Optional[str]:
        for lbl in self._aircraft_labels:
            aid, _name = self._parse_aircraft_label(lbl)
            if aid == aircraft_id:
                return lbl
        return None

    def _on_aircraft_selected(self, label: str) -> None:
        aid, name = self._parse_aircraft_label(label)
        if aid is None:
            return
        if isinstance(self.fields.get("aircraftId"), ctk.CTkEntry):
            entry: ctk.CTkEntry = self.fields["aircraftId"]  # type: ignore
            entry.configure(state="normal")
            entry.delete(0, "end")
            entry.insert(0, str(aid))
            entry.configure(state="disabled")
        if isinstance(self.fields.get("aircraftType"), tk.StringVar):
            self.fields["aircraftType"].set(name)

    def reload_aircraft_list(self) -> None:
        if self.aircraft_choice is None:
            return
        current = self.aircraft_choice.get()
        self._aircraft_labels = self._get_aircraft_labels()
        values = self._aircraft_labels or ["1 - Cessna 172"]
        self.aircraft_choice.configure(values=values)
        if current in values:
            self.aircraft_choice.set(current)
            self._on_aircraft_selected(current)
        else:
            self.aircraft_choice.set(values[0])
            self._on_aircraft_selected(values[0])

    def select_aircraft_id(self, aircraft_id: int) -> None:
        if self.aircraft_choice is None:
            return
        label = self._find_aircraft_label_by_id(int(aircraft_id))
        if label:
            self.aircraft_choice.set(label)
            self._on_aircraft_selected(label)
    def _build_sections(self) -> None:
        meta = self._section("Simulation Metadata")
        self._entry(meta, "name", "simulationName", "New Simulation")
        self._entry(meta, "description", "simulationDescription", "")
        self._entry(meta, "versionId", "versionId", "1", width=120)
        sid = self._entry(meta, "simId", "simulationId", default="1", width=120, state="disabled")
        self.fields["createdAt"] = ctk.CTkLabel(meta, text=f"Created: {_now_str()}")
        self.fields["createdAt"].pack(anchor="w", padx=8, pady=2)
        self.fields["simId_widget"] = sid

        environment = self._section("Environment Selection")
        self._entry(environment, "environmentId", "environmentId (e.g. 1 = United Kingdom)", "1")
        self._entry(environment, "weatherId", "weatherId (e.g. 1 = Warm Summer Day, 2 = Cold Winter Day)", "1")

        aircraft = self._section("Aircraft Selection")
        aircraft_row = ctk.CTkFrame(aircraft, fg_color="transparent")
        aircraft_row.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(aircraft_row, text="Select aircraft").pack(side="left", padx=4)

        self.fields["aircraftType"] = tk.StringVar(value="")
        self._aircraft_labels = self._get_aircraft_labels()
        self.aircraft_choice = ctk.CTkComboBox(
            aircraft_row,
            values=self._aircraft_labels or ["1 - Cessna 172"],
            width=360,
            command=self._on_aircraft_selected,
        )
        self.aircraft_choice.pack(side="left", padx=6)
        ctk.CTkButton(aircraft_row, text="Reload", width=90, command=self.reload_aircraft_list).pack(side="left", padx=6)

        self._entry(aircraft, "aircraftId", "aircraftId", "1", state="disabled")
        # Initialise selection
        if self._aircraft_labels:
            self.aircraft_choice.set(self._aircraft_labels[0])
            self._on_aircraft_selected(self._aircraft_labels[0])

        aero = self._section("Aerodynamic / Model Parameters")
        self._entry(aero, "regimeId", "regimeId", "1")
        self._entry(aero, "regressionDegree", "regressionDegree", "20")
        self._entry(aero, "surfaceArea", "surfaceArea", "122.0")
        self._entry(aero, "chord", "chord", "1.23")
        self._entry(aero, "blendWidth", "blendWidth (deg)", "5")
        self._entry(aero, "decayConstant", "decayConstant", "1.0")

        time_sec = self._section("Time & Integration")
        self._entry(time_sec, "dt", "dt", "0.01")
        self._entry(time_sec, "timeEnd", "timeEnd", "5.0")
        ctk.CTkLabel(time_sec, text="Integrator: RK4 (read-only)").pack(anchor="w", padx=8, pady=4)

        ssv = self._section("Initial State Space Vector (SSV)")
        self._entry(ssv, "u", "u - Forward Velocity", "50.0")
        self._entry(ssv, "w", "w - Vertical Velocity", "-2.0")
        self._entry(ssv, "q", "q - Pitch Rate", "0.05")
        self._entry(ssv, "theta", "theta - Pitch Angle", "0.1")
        self._entry(ssv, "x", "x - X Displacement", "0.0")
        self._entry(ssv, "z", "z - Altitude / Y Displacement", "1000.0")
        control = self._section("Control Configuration")
        mode_row = ctk.CTkFrame(control, fg_color="transparent")
        mode_row.pack(fill="x", padx=8, pady=2)
        self.fields["controlMode"] = tk.StringVar(value="scheduled")
        ctk.CTkLabel(mode_row, text="controlMode").pack(side="left", padx=4)
        for text, val in [("manual", "manual"), ("scheduled", "scheduled")]:
            ctk.CTkRadioButton(mode_row, text=text, variable=self.fields["controlMode"], value=val).pack(
                side="left", padx=4
            )
        self.schedule_table = ScheduleTable(control)
        self.schedule_table.pack(fill="x", padx=8, pady=4)

        stall = self._section("Stall Monitoring")
        self.fields["UseStall"] = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(stall, text="UseStall", variable=self.fields["UseStall"]).pack(anchor="w", padx=8, pady=2)
        self._entry(stall, "criticalAoa", "criticalAoa (deg)", "17")
        self._entry(stall, "stallMargin", "stallMargin", "0.95")

        kalman = self._section("Kalman Filter Configuration (Optional)")
        self.fields["kalmanEnabled"] = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(kalman, text="Enable Kalman Filter", variable=self.fields["kalmanEnabled"]).pack(
            anchor="w", padx=8, pady=2
        )
        self._entry(kalman, "initialStateEstimate", "initialStateEstimate (comma list)", "50,-2,0.1,1000")
        self._entry(kalman, "initialUncertainityEstimate", "initialUncertaintyEstimate (4x4 rows)", "0.5,0,0,0;0,0.5,0,0;0,0,0.5,0;0,0,0,0.5", width=260)
        self._entry(kalman, "processNoiseUncertainity", "processNoiseUncertainty (4x4 rows)", "0.05,0,0,0;0,0.05,0,0;0,0,0.05,0;0,0,0,0.05", width=260)
        self._entry(kalman, "sensorNoiseUncertainity", "sensorNoiseUncertainty (4x4 rows)", "0.2,0,0,0;0,0.2,0,0;0,0,0.2,0;0,0,0,0.2", width=260)

        sensor = self._section("Sensor Configuration (Optional)")
        self._entry(sensor, "sensors", "SensorManager path or leave blank", "")

        trim = self._section("Trim Solver Configuration")
        self._entry(trim, "dalpha", "dalpha", "0.05")
        self._entry(trim, "de", "de", "0.5")
        self._entry(trim, "toleration", "toleration", "1e-6")
        self._entry(trim, "maxIterations", "maxIterations", "2000")
        self._entry(trim, "alpha0Array", "alpha0Array (deg, comma list)", "-5,-2,0,2,5,8,12")
        self._entry(trim, "e0Array", "e0Array (deg, comma list)", "-15,-10,-5,0,5,10,15")
        self._entry(trim, "toleranceDuplicate", "toleranceDuplicate", "2")

        data = self._section("Data Output Settings")
        self.fields["recordRaw"] = tk.BooleanVar(value=True)
        self.fields["recordKalman"] = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(data, text="Save raw data", variable=self.fields["recordRaw"]).pack(anchor="w", padx=8, pady=2)
        ctk.CTkCheckBox(data, text="Save Kalman-filtered data", variable=self.fields["recordKalman"]).pack(
            anchor="w", padx=8, pady=2
        )
        self._entry(data, "segmentSeconds", "Segment length (seconds)", "1.0")
        vars_frame = ctk.CTkFrame(data, fg_color="transparent")
        vars_frame.pack(fill="x", padx=8, pady=4)
        self.fields["recordVars"] = {}
        for key in ["u", "w", "q", "theta", "x", "z", "elevator", "thrust", "stall", "estimate"]:
            var = tk.BooleanVar(value=True)
            ctk.CTkCheckBox(vars_frame, text=key, variable=var).pack(side="left", padx=4)
            self.fields["recordVars"][key] = var
    def load_defaults(self) -> None:
        self.fields["simId"].configure(state="normal")
        self.fields["simId"].delete(0, "end")
        self.fields["simId"].insert(0, "1")
        self.fields["simId"].configure(state="disabled")

    def load_config(self, cfg: Dict[str, Any]) -> None:
        for key, widget in self.fields.items():
            if key in cfg and isinstance(widget, ctk.CTkEntry):
                widget.configure(state="normal")
                widget.delete(0, "end")
                widget.insert(0, str(cfg[key]))
                if key == "simId":
                    widget.configure(state="disabled")
            elif key == "aircraftType" and isinstance(widget, tk.StringVar):
                widget.set(cfg.get("aircraftType", "Cessna 172"))

        # Attempt to restore aircraft selection from config (aircraftId preferred).
        try:
            if self.aircraft_choice is not None and isinstance(self.fields.get("aircraftId"), ctk.CTkEntry):
                aircraft_id = cfg.get("aircraftId")
                if aircraft_id is not None:
                    label = self._find_aircraft_label_by_id(int(float(aircraft_id)))
                    if label:
                        self.aircraft_choice.set(label)
                        self._on_aircraft_selected(label)
        except Exception:
            pass

        data_out = cfg.get("dataOutput", {})
        if isinstance(data_out, dict) and "segmentSeconds" in data_out and isinstance(self.fields.get("segmentSeconds"), ctk.CTkEntry):
            entry: ctk.CTkEntry = self.fields["segmentSeconds"]  # type: ignore
            entry.configure(state="normal")
            entry.delete(0, "end")
            entry.insert(0, str(data_out.get("segmentSeconds", 1.0)))

        if "controlSchedule" in cfg:
            self.schedule_table.load(cfg["controlSchedule"])
        if "controlMode" in cfg and isinstance(self.fields["controlMode"], tk.StringVar):
            self.fields["controlMode"].set(cfg["controlMode"])
        data_out_vars = None
        if isinstance(cfg.get("dataOutput"), dict):
            data_out_vars = cfg["dataOutput"].get("variables")
        if isinstance(data_out_vars, dict):
            for k, v in data_out_vars.items():
                if k in self.fields["recordVars"]:
                    self.fields["recordVars"][k].set(bool(v))

    def _parse_matrix(self, text: str) -> Optional[List[List[float]]]:
        try:
            rows = []
            for row in text.split(";"):
                if row.strip() == "":
                    continue
                rows.append([float(x.strip()) for x in row.split(",") if x.strip() != ""])
            return rows if rows else None
        except Exception:
            return None

    def _parse_array(self, text: str, deg: bool = False) -> Optional[List[float]]:
        try:
            arr = [float(x.strip()) for x in text.split(",") if x.strip() != ""]
            if deg:
                arr = [math.radians(x) for x in arr]
            return arr
        except Exception:
            return None

    def build_config(self) -> Tuple[Optional[Dict[str, Any]], List[str]]:
        errors: List[str] = []

        def req_float(key: str, positive: bool = False) -> float:
            val = _safe_float(self.fields[key].get())
            if val is None:
                errors.append(f"{key} must be a number")
                return 0.0
            if positive and val <= 0:
                errors.append(f"{key} must be > 0")
            return val

        cfg: Dict[str, Any] = {
            "uid": uuid.uuid4().hex[:8].upper(),
            "name": self.fields["name"].get(),
            "description": self.fields["description"].get(),
            "createdAt": _now_str(),
        }
        if not cfg["name"]:
            errors.append("simulationName is required")

        sim_id = 1
        try:
            self.fields["simId"].configure(state="normal")
            sim_id = int(float(self.fields["simId"].get()))
        except Exception:
            errors.append("simulationId must be numeric")
        finally:
            self.fields["simId"].configure(state="disabled")
        cfg["simId"] = sim_id
        cfg["versionId"] = int(req_float("versionId", positive=True))
        cfg["environmentId"] = int(req_float("environmentId", positive=True))
        cfg["weatherId"] = int(req_float("weatherId", positive=True))

        cfg["aircraftId"] = int(req_float("aircraftId", positive=True))
        cfg["aircraftType"] = self.fields["aircraftType"].get()
        cfg["regimeId"] = int(req_float("regimeId", positive=True))
        cfg["regressionDegree"] = int(req_float("regressionDegree", positive=True))
        cfg["surfaceArea"] = req_float("surfaceArea", positive=True)
        cfg["chord"] = req_float("chord", positive=True)
        cfg["blendWidth"] = math.radians(req_float("blendWidth", positive=True))
        cfg["decayConstant"] = req_float("decayConstant", positive=True)

        cfg["dt"] = req_float("dt", positive=True)
        cfg["timeEnd"] = req_float("timeEnd", positive=True)
        if cfg["timeEnd"] <= cfg["dt"]:
            errors.append("timeEnd must be greater than dt")

        cfg["initialState"] = [
            req_float("u"),
            req_float("w"),
            req_float("q"),
            req_float("theta"),
            req_float("x"),
            req_float("z"),
        ]

        cfg["controlMode"] = self.fields["controlMode"].get()
        cfg["controlSchedule"] = []
        for row in self.schedule_table.rows:
            vals = {k: _safe_float(row[k].get()) for k in ["start", "end", "elevator", "thrust"]}
            if None in vals.values():
                errors.append("Control schedule rows must be numeric")
                continue
            if vals["end"] <= vals["start"]:  # type: ignore
                errors.append("Control schedule end must be greater than start")
                continue
            cfg["controlSchedule"].append(vals)
        if cfg["controlMode"] == "scheduled" and not cfg["controlSchedule"]:
            errors.append("At least one control schedule row is required for scheduled mode")

        cfg["UseStall"] = bool(self.fields["UseStall"].get())
        if cfg["UseStall"]:
            cfg["criticalAoa"] = math.radians(req_float("criticalAoa", positive=True))
            cfg["stallMargin"] = req_float("stallMargin", positive=True)
        else:
            cfg["criticalAoa"] = 0.0
            cfg["stallMargin"] = 0.0

        if self.fields["kalmanEnabled"].get():
            init_state = self._parse_array(self.fields["initialStateEstimate"].get())
            m1 = self._parse_matrix(self.fields["initialUncertainityEstimate"].get())
            m2 = self._parse_matrix(self.fields["processNoiseUncertainity"].get())
            m3 = self._parse_matrix(self.fields["sensorNoiseUncertainity"].get())
            if not (init_state and m1 and m2 and m3):
                errors.append("Kalman matrices must be valid numbers")
            else:
                cfg["kalman"] = {
                    "initialStateEstimate": init_state,
                    "initialUncertainityEstimate": m1,
                    "processNoiseUncertainity": m2,
                    "sensorNoiseUncertainity": m3,
                }
        else:
            cfg["kalman"] = None

        sensors_path = self.fields["sensors"].get().strip()
        cfg["sensors"] = None
        if sensors_path:
            cfg["sensors"] = sensors_path

        trim_alpha = self._parse_array(self.fields["alpha0Array"].get(), deg=True)
        trim_e = self._parse_array(self.fields["e0Array"].get(), deg=True)
        cfg["trimSolver"] = {
            "dalpha": math.radians(req_float("dalpha", positive=True)),
            "de": math.radians(req_float("de", positive=True)),
            "toleration": req_float("toleration", positive=True),
            "maxIterations": int(req_float("maxIterations", positive=True)),
            "alpha0Array": trim_alpha or [],
            "e0Array": trim_e or [],
            "toleranceDuplicate": req_float("toleranceDuplicate", positive=True),
        }
        if trim_alpha is None or trim_e is None:
            errors.append("Trim solver arrays must be numeric lists")

        cfg["dataOutput"] = {
            "recordRaw": bool(self.fields["recordRaw"].get()),
            "recordKalman": bool(self.fields["recordKalman"].get()),
            "variables": {k: bool(v.get()) for k, v in self.fields["recordVars"].items()},
            "segmentSeconds": req_float("segmentSeconds", positive=True),
        }

        return (cfg if not errors else None, errors)

    def show_errors(self, errors: List[str]) -> None:
        if errors:
            self.error_label.configure(text="; ".join(errors))
        else:
            self.error_label.configure(text="")
class ScheduleTable(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame) -> None:
        super().__init__(parent, fg_color="#0f172a", corner_radius=8)
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=4, pady=4)
        ctk.CTkLabel(header, text="Control Schedule (start, end, elevator, thrust)").pack(side="left", padx=4)
        ctk.CTkButton(header, text="+ Row", width=60, command=self.add_row).pack(side="right", padx=2)

        self.rows_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.rows_frame.pack(fill="x", padx=4, pady=4)
        self.rows: List[Dict[str, ctk.CTkEntry]] = []
        self.add_row()

    def add_row(self, values: Optional[Dict[str, Any]] = None) -> None:
        row_frame = ctk.CTkFrame(self.rows_frame, fg_color="#111827", corner_radius=6)
        row_frame.pack(fill="x", pady=2)
        row: Dict[str, ctk.CTkEntry] = {}
        defaults = {"start": 0.0, "end": 1.0, "elevator": 0.0, "thrust": 500.0}
        if values:
            defaults.update({k: values.get(k, defaults[k]) for k in defaults})
        for key, width in [("start", 80), ("end", 80), ("elevator", 100), ("thrust", 100)]:
            entry = ctk.CTkEntry(row_frame, width=width)
            entry.insert(0, str(defaults[key]))
            entry.pack(side="left", padx=4, pady=4)
            row[key] = entry

        def remove_row():
            row_frame.destroy()
            self.rows.remove(row)

        ctk.CTkButton(row_frame, text="Remove", width=70, command=remove_row).pack(side="right", padx=4)
        self.rows.append(row)

    def load(self, schedules: List[Dict[str, Any]]) -> None:
        for row in list(self.rows):
            row_frame = row["start"].master
            row_frame.destroy()
        self.rows.clear()
        for s in schedules:
            self.add_row(s)
class LiveDashboardScreen(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame, on_cancel, on_pause=None, on_export=None) -> None:
        super().__init__(parent, fg_color="#0b1220")
        self.on_cancel = on_cancel
        self.on_pause = on_pause
        self.on_export = on_export

        if FlightTestDashboard is None:
            ctk.CTkLabel(self, text="Dashboard backend not available.", text_color="red").pack(padx=20, pady=20)
            self.dashboard = None
            return

        self.dashboard = FlightTestDashboard(
            self,
            on_abort=self.on_cancel,
            on_pause=self.on_pause,
            on_export=self.on_export,
        )
        self.dashboard.pack(fill="both", expand=True)

    def reset_dashboard(self, cfg: Dict[str, Any]) -> None:
        if self.dashboard is None:
            return
        critical = cfg.get("criticalAoa") if cfg.get("UseStall") else None
        try:
            critical = float(critical) if critical is not None else None
        except Exception:
            critical = None
        self.dashboard.reset(critical_aoa=critical)

    def update_snapshot(self, snap) -> None:
        if self.dashboard is None:
            return
        self.dashboard.update(snap)

    def log_event(self, message: str) -> None:
        if self.dashboard is None:
            return
        self.dashboard.log_event(message)

    def show_error(self, message: str) -> None:
        if self.dashboard is not None:
            self.dashboard.log_event(message)
        popup = ctk.CTkToplevel(self)
        popup.title("Simulation Error")
        popup.configure(fg_color="#111827")
        ctk.CTkLabel(popup, text=message, text_color="red", wraplength=420).pack(padx=20, pady=20)
        ctk.CTkButton(popup, text="Close", command=popup.destroy).pack(pady=6)
class Gauge(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame, title: str, units: str, max_value: float) -> None:
        super().__init__(parent, fg_color="#0f172a", corner_radius=10)
        self.max_value = max_value
        self.units = units
        ctk.CTkLabel(self, text=title, font=ctk.CTkFont(weight="bold")).pack(pady=(6, 0))
        self.canvas = tk.Canvas(self, width=180, height=140, bg="#0f172a", highlightthickness=0)
        self.canvas.pack(padx=8, pady=4)
        self.value_label = ctk.CTkLabel(self, text="0.0")
        self.value_label.pack()
        self.unit_label = ctk.CTkLabel(self, text=units, text_color="#9ca3af")
        self.unit_label.pack(pady=(0, 8))
        self.value = 0.0
        self._render()

    def update_value(self, value: float) -> None:
        self.value = value
        self._render()

    def set_scale(self, max_value: float) -> None:
        self.max_value = max_value

    def _render(self) -> None:
        self.canvas.delete("all")
        
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        
        if w <= 1 or h <= 1:
            w = 180
            h = 140
        
        center_x = w / 2
        center_y = h / 2
        radius = min(w, h) / 2 - 10
        
        start_angle = 180
        arc_extent = 180
        
        bbox_x1 = center_x - radius
        bbox_y1 = center_y - radius
        bbox_x2 = center_x + radius
        bbox_y2 = center_y + radius
        
        self.canvas.create_arc(bbox_x1, bbox_y1, bbox_x2, bbox_y2, start=start_angle, extent=arc_extent, style="arc", outline="#374151", width=4)
        
        percent = 0.0
        if self.max_value > 0:
            percent = max(0.0, min(1.0, self.value / self.max_value))
        
        self.canvas.create_arc(bbox_x1, bbox_y1, bbox_x2, bbox_y2, start=start_angle, extent=arc_extent * percent, style="arc", outline="#3b82f6", width=6)
        
        self.value_label.configure(text=f"{self.value:.2f}")
class SummaryScreen(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame, on_menu, on_history) -> None:
        super().__init__(parent, fg_color="#0b1220")
        self.on_menu = on_menu
        self.on_history = on_history
        
        # Header
        header = ctk.CTkFrame(self, fg_color="#0b1220")
        header.pack(fill="x", pady=6)
        ctk.CTkLabel(header, text="Simulation Summary", font=ctk.CTkFont(size=20, weight="bold")).pack(
            side="left", padx=6
        )
        ctk.CTkButton(header, text="Main Menu", width=120, command=self.on_menu).pack(side="right", padx=4)
        ctk.CTkButton(header, text="History", width=120, command=self.on_history).pack(side="right", padx=4)

        # Status banner
        self.status_frame = ctk.CTkFrame(self, fg_color="#0f172a", corner_radius=12)
        self.status_frame.pack(fill="x", padx=12, pady=(0, 12))
        
        self.status_label = ctk.CTkLabel(
            self.status_frame, 
            text="", 
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.status_label.pack(pady=12)
        
        # Key metrics cards
        self.metrics_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.metrics_frame.pack(fill="x", padx=12, pady=(0, 12))
        
        # Row 1: Duration and Status details
        row1 = ctk.CTkFrame(self.metrics_frame, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 8))
        
        self.duration_card = self._create_metric_card(row1, "Duration", "0.00s", "#3b82f6", "TIME")
        self.duration_card.pack(side="left", expand=True, fill="x", padx=(0, 4))
        
        self.message_card = self._create_metric_card(row1, "Status Message", "N/A", "#6b7280", "INFO")
        self.message_card.pack(side="left", expand=True, fill="x", padx=(4, 0))
        
        # Row 2: Performance metrics
        row2 = ctk.CTkFrame(self.metrics_frame, fg_color="transparent")
        row2.pack(fill="x", pady=(0, 8))
        
        self.airspeed_card = self._create_metric_card(row2, "Max Airspeed", "0.00 m/s", "#22c55e", "SPEED")
        self.airspeed_card.pack(side="left", expand=True, fill="x", padx=(0, 4))
        
        self.lift_drag_card = self._create_metric_card(row2, "Max L/D Ratio", "0.00", "#a855f7", "AERO")
        self.lift_drag_card.pack(side="left", expand=True, fill="x", padx=(4, 0))
        
        # Row 3: More metrics
        row3 = ctk.CTkFrame(self.metrics_frame, fg_color="transparent")
        row3.pack(fill="x", pady=(0, 8))
        
        self.pitch_rate_card = self._create_metric_card(row3, "Max Pitch Rate", "0.000 rad/s", "#f97316", "RATE")
        self.pitch_rate_card.pack(side="left", expand=True, fill="x", padx=(0, 4))
        
        self.trim_card = self._create_metric_card(row3, "Trim Tolerance", "N/A", "#10b981", "TRIM")
        self.trim_card.pack(side="left", expand=True, fill="x", padx=(4, 0))
        
        # Configuration section
        config_header = ctk.CTkFrame(self, fg_color="#0f172a", corner_radius=12)
        config_header.pack(fill="x", padx=12, pady=(0, 8))
        ctk.CTkLabel(
            config_header, 
            text="Configuration Details", 
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=10)
        
        self.config_box = ctk.CTkTextbox(
            self, 
            height=200, 
            fg_color="#0f172a", 
            text_color="#e5e7eb",
            font=ctk.CTkFont(size=11)
        )
        self.config_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        # Event lookup section (time-indexed retrieval + hash validation)
        self.lookup_frame = ctk.CTkFrame(self, fg_color="#0f172a", corner_radius=12)
        self.lookup_frame.pack(fill="x", padx=12, pady=(0, 12))
        ctk.CTkLabel(
            self.lookup_frame,
            text="Event-Indexed Data Lookup",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(anchor="w", padx=12, pady=(10, 6))

        row = ctk.CTkFrame(self.lookup_frame, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(row, text="Time (s):", text_color="#9ca3af").pack(side="left")
        self.lookup_time = ctk.CTkEntry(row, width=140)
        self.lookup_time.insert(0, "0.0")
        self.lookup_time.pack(side="left", padx=8)
        self.lookup_button = ctk.CTkButton(row, text="Find", width=90, command=self._on_lookup)
        self.lookup_button.pack(side="left", padx=4)

        self.lookup_result = ctk.CTkLabel(self.lookup_frame, text="", text_color="#e5e7eb", justify="left")
        self.lookup_result.pack(anchor="w", padx=12, pady=(0, 12))

        self._active_log_path: Optional[Path] = None
        self._active_index_path: Optional[Path] = None

    def _create_metric_card(self, parent, title, value, color, icon):
        """Create a metric card with icon, title, and value"""
        card = ctk.CTkFrame(parent, fg_color="#111827", corner_radius=12)
        
        # Icon and content frame
        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=12, pady=12)
        
        # Icon (using text-based icons)
        icon_label = ctk.CTkLabel(
            content, 
            text=f"[{icon}]", 
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=color
        )
        icon_label.pack(anchor="w", pady=(0, 4))
        
        # Title
        title_label = ctk.CTkLabel(
            content, 
            text=title, 
            text_color="#9ca3af",
            font=ctk.CTkFont(size=12)
        )
        title_label.pack(anchor="w")
        
        # Value
        value_label = ctk.CTkLabel(
            content, 
            text=value, 
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=color
        )
        value_label.pack(anchor="w", pady=(2, 0))
        
        # Store references for updating
        card.value_label = value_label
        card.title_label = title_label
        
        return card

    def show_summary(self, summary: Dict[str, Any], cfg: Dict[str, Any]) -> None:
        # Update status banner
        success = summary.get('success', False)
        status_text = "SUCCESS: Simulation Completed Successfully" if success else "FAILED: Simulation Failed"
        status_color = "#22c55e" if success else "#ef4444"
        self.status_label.configure(text=status_text, text_color=status_color)
        
        # Update metric cards
        self.duration_card.value_label.configure(text=f"{summary.get('duration', 0):.2f}s")
        self.message_card.value_label.configure(text=summary.get('message', 'N/A'))
        self.airspeed_card.value_label.configure(text=f"{summary.get('maxAirspeed', 0):.2f} m/s")
        self.lift_drag_card.value_label.configure(text=f"{summary.get('maxLiftToDrag', 0):.2f}")
        self.pitch_rate_card.value_label.configure(text=f"{summary.get('maxPitchRate', 0):.3f} rad/s")
        self.trim_card.value_label.configure(text=str(summary.get('trimResult', 'N/A')))
        
        # Update configuration details
        config_lines = [
            f"Simulation: {cfg.get('name', 'Unnamed')}",
            f"Created: {summary.get('time', 'N/A')}",
            f"Aircraft: {cfg.get('aircraftType', 'N/A')}",
            f"Time Step: {cfg.get('dt', 'N/A')}s",
            f"End Time: {cfg.get('timeEnd', 'N/A')}s",
            "",
            "Key Settings:",
            f"  - Control Mode: {cfg.get('controlMode', 'N/A')}",
            f"  - Stall Protection: {'Enabled' if cfg.get('UseStall', False) else 'Disabled'}",
            f"  - Kalman Filter: {'Enabled' if cfg.get('kalman') else 'Disabled'}",
            f"  - Data Recording: {'Enabled' if cfg.get('dataOutput', {}).get('recordRaw', False) else 'Disabled'}",
        ]
        
        self.config_box.delete("1.0", "end")
        self.config_box.insert("end", "\n".join(config_lines))

        # The app stores paths in the history entry; when viewing a fresh run,
        # we don't have those paths here, so the parent app sets them after persistence.
        self.lookup_result.configure(text="Enter a time (seconds) to retrieve the SSV row and validate its segment hash.")

    def set_event_index_paths(self, log_path: Optional[str], index_path: Optional[str]) -> None:
        self._active_log_path = Path(log_path) if log_path else None
        self._active_index_path = Path(index_path) if index_path else None

    def _on_lookup(self) -> None:
        if EventLookup is None:
            self.lookup_result.configure(text="Event lookup unavailable (module import failed).", text_color="#ef4444")
            return
        if not self._active_log_path or not self._active_index_path:
            self.lookup_result.configure(text="No log/index paths available for lookup.", text_color="#ef4444")
            return
        t = _safe_float(self.lookup_time.get())
        if t is None:
            self.lookup_result.configure(text="Time must be numeric.", text_color="#ef4444")
            return
        if not self._active_log_path.exists() or not self._active_index_path.exists():
            self.lookup_result.configure(text="Log or index file not found.", text_color="#ef4444")
            return

        try:
            row, valid, seg = EventLookup.lookup_and_validate(self._active_log_path, self._active_index_path, float(t))
        except Exception as exc:
            traceback.print_exc()
            self.lookup_result.configure(text=f"Lookup failed: {exc}", text_color="#ef4444")
            return

        if row is None or seg is None:
            self.lookup_result.configure(text="No data found.", text_color="#ef4444")
            return

        state = [row["u"], row["w"], row["q"], row["theta"], row["x"], row["z"]]
        validation = "VALID" if valid else "HASH MISMATCH"
        color = "#22c55e" if valid else "#ef4444"
        self.lookup_result.configure(
            text=(
                f"{validation} | segment {seg.segment_id} rows {seg.row_start}-{seg.row_end} "
                f"t={row['Time']:.3f}s\n"
                f"SSV [u,w,q,theta,x,z] = {state} | elevator={row['elevator']:.4f} thrust={row['thrust']:.1f} stall={row['stall']}"
            ),
            text_color=color,
        )
class HistoryScreen(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame, history: List[Dict[str, Any]], on_view, on_reload, on_delete, on_menu):
        super().__init__(parent, fg_color="#0b1220")
        self.history = history
        self.on_view = on_view
        self.on_reload = on_reload
        self.on_delete = on_delete
        self.on_menu = on_menu

        header = ctk.CTkFrame(self, fg_color="#0b1220")
        header.pack(fill="x", pady=6)
        ctk.CTkLabel(header, text="Previous Simulations", font=ctk.CTkFont(size=20, weight="bold")).pack(
            side="left", padx=6
        )
        ctk.CTkButton(header, text="Main Menu", command=self.on_menu).pack(side="right", padx=6)

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="#0f172a", height=640)
        self.list_frame.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh(self.history)

    def refresh(self, history: List[Dict[str, Any]]) -> None:
        for child in self.list_frame.winfo_children():
            child.destroy()
        for item in history:
            card = ctk.CTkFrame(self.list_frame, fg_color="#111827", corner_radius=10)
            card.pack(fill="x", padx=6, pady=4)
            title = f"{item.get('name')} ({item.get('uid')})"
            meta = f"{item.get('created', '')} | {item.get('aircraft', '')} | Duration {item.get('duration', '')}s"
            ctk.CTkLabel(card, text=title, font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=8, pady=2)
            ctk.CTkLabel(card, text=meta, text_color="#9ca3af").pack(anchor="w", padx=8, pady=2)
            metrics = (
                f"Max Airspeed: {self._as_float(item.get('maxAirspeed', 0)):.2f}  |  "
                f"Max L/D: {self._as_float(item.get('maxLiftToDrag', 0)):.2f}  |  "
                f"Max Pitch Rate: {self._as_float(item.get('maxPitchRate', 0)):.3f}  |  "
                f"Trim: {item.get('trimResult', 'n/a')}"
            )
            ctk.CTkLabel(card, text=metrics).pack(anchor="w", padx=8, pady=2)
            btns = ctk.CTkFrame(card, fg_color="transparent")
            btns.pack(anchor="e", padx=8, pady=4)
            ctk.CTkButton(btns, text="View Summary", width=110, command=lambda i=item: self.on_view(i)).pack(
                side="left", padx=4
            )
            ctk.CTkButton(btns, text="Reload Config", width=110, command=lambda i=item: self.on_reload(i)).pack(
                side="left", padx=4
            )
            ctk.CTkButton(btns, text="Delete", width=90, fg_color="#ef4444", command=lambda i=item: self.on_delete(i)).pack(
                side="left", padx=4
            )

    @staticmethod
    def _as_float(value: Any) -> float:
        try:
            return float(value)
        except Exception:
            return 0.0

def main() -> None:
    app = FlightSimApp()
    app.mainloop()


if __name__ == "__main__":
    main()
