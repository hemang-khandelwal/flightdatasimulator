
"""
Flight Dynamics Simulator UI
- Collects and validates inputs
- Calls the simulation backend
- Streams live results and handles failures
- Persists and reloads simulation metadata
"""
from __future__ import annotations

import datetime
import json
import math
import sys
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
    from SimulationRun.SimulationBuilder import SimulationBuilder
    from SimulationRun.SimulationRUN import SimulationRun
except Exception:
    SimulationBuilder = None  # type: ignore
    SimulationRun = None  # type: ignore

def _now_str() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _safe_float(value: str) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return None
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
        self.target_time: float = 0.0
        self.running = False
        self.after_id: Optional[str] = None
        self.lift_drag_points: List[Tuple[float, float]] = []
        self.history = self._load_history()

        self.container = ctk.CTkFrame(self, fg_color="#0b1220")
        self.container.pack(fill="both", expand=True, padx=12, pady=12)

        self.screens: Dict[str, ctk.CTkFrame] = {}
        self._build_screens()
        self.show_screen("menu")
    def _build_screens(self) -> None:
        self.screens["menu"] = MainMenuScreen(
            self.container,
            on_new=lambda: self.show_screen("config"),
            on_history=lambda: self.show_screen("history"),
        )
        self.screens["config"] = ConfigScreen(
            self.container,
            on_run=self.start_simulation,
            on_menu=lambda: self.show_screen("menu"),
        )
        self.screens["live"] = LiveDashboardScreen(
            self.container,
            on_cancel=self.stop_simulation,
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

    def show_screen(self, name: str) -> None:
        for child in self.container.winfo_children():
            child.pack_forget()
        screen = self.screens[name]
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

        try:
            self.domain = SimulationBuilder.build(cfg)
            self.engine = SimulationRun.create(
                cfg,
                self.domain["controls"],
                self.domain["integrator"],
                self.domain.get("sensors"),
                self.domain.get("kalman"),
                self.domain.get("stall"),
            )
        except Exception as exc:
            self.screens["config"].show_errors([f"Failed to prepare simulation: {exc}"])  # type: ignore
            return

        live_screen: LiveDashboardScreen = self.screens["live"]  # type: ignore
        live_screen.reset_dashboard(cfg)
        self.show_screen("live")
        self.running = True
        self._step_loop()
    def _step_loop(self) -> None:
        if not self.running or self.engine is None:
            return
        try:
            self.engine.step()
        except Exception as exc:
            self._handle_runtime_error(f"Simulation crashed: {exc}")
            return

        ctx = self.engine.ctx
        live_screen: LiveDashboardScreen = self.screens["live"]  # type: ignore

        state = np.array(ctx.trueState).flatten()
        airspeed = float(np.linalg.norm(state[:2])) if state.size >= 2 else 0.0
        altitude = float(state[5]) if state.size >= 6 else 0.0
        x_disp = float(state[4]) if state.size >= 5 else 0.0
        z_disp = altitude

        lift, drag = self._estimate_lift_drag(state)
        self.lift_drag_points.append((drag, lift))
        live_screen.update_dashboard(
            time_val=ctx.t,
            airspeed=airspeed,
            altitude=altitude,
            x_disp=x_disp,
            z_disp=z_disp,
            lift=lift,
            drag=drag,
            measurement=ctx.measurement,
            estimate=ctx.stateEstimate,
        )
        # Note: stall state is shown but does not abort; gauges continue running
        if getattr(ctx, "stalled", False):
            live_screen.status_label.configure(text=f"Stall detected at t={ctx.t:.2f}s")
        else:
            live_screen.status_label.configure(text="")

        if self._has_numeric_failure(ctx, state):
            return

        if ctx.t >= self.target_time:
            self._finish_run(success=True)
            return

        self.after_id = self.after(40, self._step_loop)

    def _estimate_lift_drag(self, state: np.ndarray) -> Tuple[float, float]:
        lift = 0.0
        drag = 0.0
        try:
            if "forces" in self.domain and "environment" in self.domain:
                u = float(state[0]) if state.size > 0 else 0.0
                w = float(state[1]) if state.size > 1 else 0.0
                v_res = math.sqrt(u * u + w * w)
                aoa = math.atan2(w, u) if v_res > 1e-9 else 0.0
                density = 1.225
                env = self.domain["environment"]
                if hasattr(env, "density"):
                    density = float(env.density(state[5] if state.size >= 6 else 0.0))
                lift, drag, _ = self.domain["forces"].aeroForces(density, v_res, aoa, True)
        except Exception:
            lift, drag = 0.0, 0.0
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
                        state = np.array(row.get("True State") or []).flatten()
                        vals = [row.get("Time", 0.0)]
                        vals.extend([state[i] if i < state.size else "" for i in range(6)])
                        vals.append(row.get("Elevator", ""))
                        vals.append(row.get("Thrust", ""))
                        vals.append(row.get("Stall", ""))
                        f.write(",".join(map(str, vals)) + "\n")
            except Exception:
                pass

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
    def __init__(self, parent: ctk.CTkFrame, on_new, on_history) -> None:
        super().__init__(parent, fg_color="#0b1220")
        ctk.CTkLabel(self, text="Flight Data Simulator", font=ctk.CTkFont(size=26, weight="bold")).pack(
            pady=(40, 10)
        )
        ctk.CTkLabel(self, text="By Hemang Khandelwal", text_color="#9ca3af").pack(pady=(0, 30))
        ctk.CTkLabel(self, text="Select an option to begin", text_color="#9ca3af").pack(pady=(0, 30))
        ctk.CTkButton(self, text="New Simulation", width=240, height=60, command=on_new).pack(pady=10)
        ctk.CTkButton(self, text="View Previous Simulations", width=240, height=60, command=on_history).pack(pady=10)
class ConfigScreen(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame, on_run, on_menu) -> None:
        super().__init__(parent, fg_color="#0b1220")
        self.on_run = on_run
        self.error_label = ctk.CTkLabel(self, text="", text_color="red")

        self.fields: Dict[str, Any] = {}

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
    def _build_sections(self) -> None:
        meta = self._section("Simulation Metadata")
        self._entry(meta, "name", "simulationName", "New Simulation")
        self._entry(meta, "description", "simulationDescription", "")
        sid = self._entry(meta, "simId", "simulationId", default="1", width=120, state="disabled")
        self.fields["createdAt"] = ctk.CTkLabel(meta, text=f"Created: {_now_str()}")
        self.fields["createdAt"].pack(anchor="w", padx=8, pady=2)
        self.fields["simId_widget"] = sid

        aircraft = self._section("Aircraft Selection")
        aircraft_row = ctk.CTkFrame(aircraft, fg_color="transparent")
        aircraft_row.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(aircraft_row, text="aircraftType").pack(side="left", padx=4)
        self.fields["aircraftType"] = tk.StringVar(value="Cessna 172")
        for text, val in [("Cessna 172", "Cessna 172"), ("User-Defined", "User-Defined Aircraft")]:
            ctk.CTkRadioButton(aircraft_row, text=text, variable=self.fields["aircraftType"], value=val).pack(
                side="left", padx=6
            )
        self._entry(aircraft, "aircraftId", "aircraftId", "1")

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
        if "controlSchedule" in cfg:
            self.schedule_table.load(cfg["controlSchedule"])
        if "controlMode" in cfg and isinstance(self.fields["controlMode"], tk.StringVar):
            self.fields["controlMode"].set(cfg["controlMode"])
        if "recordVars" in cfg:
            for k, v in cfg["recordVars"].items():
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
    def __init__(self, parent: ctk.CTkFrame, on_cancel) -> None:
        super().__init__(parent, fg_color="#0b1220")
        self.on_cancel = on_cancel
        self.plot_points: List[Tuple[float, float]] = []
        self.plot_bounds: Optional[Tuple[float, float, float, float]] = None  # min_drag, max_drag, min_lift, max_lift

        header = ctk.CTkFrame(self, fg_color="#0b1220")
        header.pack(fill="x", pady=6)
        ctk.CTkLabel(header, text="Run Simulation (Live Dashboard)", font=ctk.CTkFont(size=20, weight="bold")).pack(
            side="left", padx=6
        )
        ctk.CTkButton(header, text="Abort", fg_color="#ef4444", command=self.on_cancel).pack(side="right", padx=6)

        top = ctk.CTkFrame(self, fg_color="#0b1220")
        top.pack(fill="x", padx=8, pady=6)
        self.airspeed_gauge = Gauge(top, "Airspeed", units="m/s", max_value=200.0)
        self.altitude_gauge = Gauge(top, "Altitude", units="m", max_value=2000.0)
        self.airspeed_gauge.pack(side="left", padx=10, pady=4)
        self.altitude_gauge.pack(side="left", padx=10, pady=4)

        metrics = ctk.CTkFrame(top, fg_color="#0f172a", corner_radius=10)
        metrics.pack(side="left", fill="both", expand=True, padx=6, pady=4)
        ctk.CTkLabel(metrics, text="Displacements", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=8, pady=4)
        self.x_label = ctk.CTkLabel(metrics, text="X: 0.0")
        self.z_label = ctk.CTkLabel(metrics, text="Z: 0.0")
        self.x_label.pack(anchor="w", padx=10, pady=2)
        self.z_label.pack(anchor="w", padx=10, pady=2)

        live_plot_frame = ctk.CTkFrame(self, fg_color="#0f172a", corner_radius=10)
        live_plot_frame.pack(fill="both", expand=True, padx=6, pady=6)
        ctk.CTkLabel(live_plot_frame, text="Lift vs Drag (real time)", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=8, pady=4
        )
        self.plot_canvas = tk.Canvas(live_plot_frame, bg="#0b1220", height=280, highlightthickness=0)
        self.plot_canvas.pack(fill="both", expand=True, padx=8, pady=8)

        bottom = ctk.CTkFrame(self, fg_color="#0b1220")
        bottom.pack(fill="x", padx=6, pady=6)

        sensor_frame = ctk.CTkFrame(bottom, fg_color="#0f172a", corner_radius=10)
        sensor_frame.pack(side="left", fill="both", expand=True, padx=6)
        ctk.CTkLabel(sensor_frame, text="Sensor vs Kalman", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=8, pady=4
        )
        table = ctk.CTkFrame(sensor_frame, fg_color="transparent")
        table.pack(fill="x", padx=6, pady=4)
        self.sensor_rows: Dict[str, Tuple[ctk.CTkLabel, ctk.CTkLabel]] = {}
        for label, key, units in [
            ("Forward Velocity (u)", "u", "m/s"),
            ("Vertical Velocity (w)", "w", "m/s"),
            ("Pitch Angle (theta)", "theta", "rad"),
            ("Altitude (z)", "z", "m"),
        ]:
            row = ctk.CTkFrame(table, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=label, width=180, anchor="w").pack(side="left", padx=4)
            sensor_lbl = ctk.CTkLabel(row, text=f"Sensor: - {units}", text_color="#9ca3af")
            kalman_lbl = ctk.CTkLabel(row, text=f"Kalman: - {units}", text_color="#9ca3af")
            sensor_lbl.pack(side="left", padx=4)
            kalman_lbl.pack(side="left", padx=12)
            self.sensor_rows[key] = (sensor_lbl, kalman_lbl)

        self.status_label = ctk.CTkLabel(self, text="", text_color="red")
        self.status_label.pack(fill="x", padx=8, pady=4)
    def reset_dashboard(self, cfg: Dict[str, Any]) -> None:
        self.plot_points = []
        self.plot_bounds = None
        init = cfg.get("initialState", [0, 0, 0, 0, 0, 0])
        try:
            speed0 = float(math.hypot(init[0], init[1]))
        except Exception:
            speed0 = 0.0
        try:
            alt0 = float(init[5])
        except Exception:
            alt0 = 0.0
        self.airspeed_gauge.set_scale(max(50.0, speed0 * 1.5 + 20.0))
        self.altitude_gauge.set_scale(max(100.0, abs(alt0) * 1.25 + 50.0))
        self.airspeed_gauge.update_value(0.0)
        self.altitude_gauge.update_value(0.0)
        self.x_label.configure(text="X: 0.0")
        self.z_label.configure(text="Z: 0.0")
        for sensor_lbl, kalman_lbl in self.sensor_rows.values():
            units = sensor_lbl.cget("text").split()[-1]
            base_s = sensor_lbl.cget("text").split(":")[0]
            base_k = kalman_lbl.cget("text").split(":")[0]
            sensor_lbl.configure(text=f"{base_s}: - {units}")
            kalman_lbl.configure(text=f"{base_k}: - {units}")
        self.status_label.configure(text="")
        self._draw_plot()

    def update_dashboard(
        self,
        time_val: float,
        airspeed: float,
        altitude: float,
        x_disp: float,
        z_disp: float,
        lift: float,
        drag: float,
        measurement: Any,
        estimate: Any,
    ) -> None:
        self.airspeed_gauge.update_value(airspeed)
        self.altitude_gauge.update_value(altitude)
        self.x_label.configure(text=f"X displacement: {x_disp:.2f}")
        self.z_label.configure(text=f"Z displacement: {z_disp:.2f}")
        self._update_sensor_table(measurement, estimate)
        if drag or lift:
            self.plot_points.append((drag, lift))
            self._update_plot_bounds(drag, lift)
            self._draw_plot()

    def _draw_plot(self) -> None:
        canvas = self.plot_canvas
        canvas.delete("all")
        w = canvas.winfo_width() or 600
        h = canvas.winfo_height() or 280
        canvas.create_line(40, h - 40, w - 20, h - 40, fill="#374151")
        canvas.create_line(40, h - 20, 40, 20, fill="#374151")
        if not self.plot_points or self.plot_bounds is None:
            return
        min_d, max_d, min_l, max_l = self.plot_bounds
        span_d = max_d - min_d if max_d != min_d else 1.0
        span_l = max_l - min_l if max_l != min_l else 1.0
        pts = []
        for d, l in self.plot_points:
            x = 40 + ((d - min_d) / span_d) * (w - 60)
            y = (h - 40) - ((l - min_l) / span_l) * (h - 80)
            pts.append((x, y))
        for i in range(1, len(pts)):
            canvas.create_line(pts[i - 1][0], pts[i - 1][1], pts[i][0], pts[i][1], fill="#3b82f6", width=2)
        x, y = pts[-1]
        canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill="#fbbf24", outline="")

    def _update_plot_bounds(self, drag: float, lift: float) -> None:
        if self.plot_bounds is None:
            pad_d = max(1.0, abs(drag) * 0.2)
            pad_l = max(1.0, abs(lift) * 0.2)
            self.plot_bounds = (drag - pad_d, drag + pad_d, lift - pad_l, lift + pad_l)
            return
        min_d, max_d, min_l, max_l = self.plot_bounds
        if drag < min_d:
            min_d = drag
        if drag > max_d:
            max_d = drag
        if lift < min_l:
            min_l = lift
        if lift > max_l:
            max_l = lift
        self.plot_bounds = (min_d, max_d, min_l, max_l)

    def _update_sensor_table(self, measurement: Any, estimate: Any) -> None:
        def get_val(source, idx):
            if source is None:
                return None
            try:
                if isinstance(source, dict):
                    mapping = {"u": source.get("u"), "w": source.get("w"), "theta": source.get("theta"), "z": source.get("z")}
                    return mapping.get(idx)
                seq = list(source)
                map_idx = {"u": 0, "w": 1, "theta": 2, "z": 3}
                pos = map_idx.get(idx)
                if pos is not None and pos < len(seq):
                    return float(seq[pos])
            except Exception:
                return None
            return None

        for key, (sensor_lbl, kalman_lbl) in self.sensor_rows.items():
            s_val = get_val(measurement, key)
            k_val = get_val(estimate, key)
            units = sensor_lbl.cget("text").split()[-1]
            sensor_lbl.configure(text=f"Sensor: {s_val:.2f} {units}" if s_val is not None else f"Sensor: - {units}")
            kalman_lbl.configure(text=f"Kalman: {k_val:.2f} {units}" if k_val is not None else f"Kalman: - {units}")

    def show_error(self, message: str) -> None:
        self.status_label.configure(text=message)
        popup = ctk.CTkToplevel(self)
        popup.title("Simulation Error")
        popup.configure(fg_color="#111827")
        ctk.CTkLabel(popup, text=message, text_color="red", wraplength=360).pack(padx=20, pady=20)
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
        w = 180
        h = 140
        start = 180
        extent = 180
        self.canvas.create_arc(10, 10, w - 10, h + 60, start=start, extent=extent, style="arc", outline="#374151", width=4)
        percent = 0.0
        if self.max_value > 0:
            percent = max(0.0, min(1.0, self.value / self.max_value))
        self.canvas.create_arc(
            10, 10, w - 10, h + 60, start=start, extent=extent * percent, style="arc", outline="#3b82f6", width=6
        )
        self.value_label.configure(text=f"{self.value:.2f}")
class SummaryScreen(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame, on_menu, on_history) -> None:
        super().__init__(parent, fg_color="#0b1220")
        self.on_menu = on_menu
        self.on_history = on_history
        header = ctk.CTkFrame(self, fg_color="#0b1220")
        header.pack(fill="x", pady=6)
        ctk.CTkLabel(header, text="Simulation Summary", font=ctk.CTkFont(size=20, weight="bold")).pack(
            side="left", padx=6
        )
        ctk.CTkButton(header, text="Main Menu", width=120, command=self.on_menu).pack(side="right", padx=4)
        ctk.CTkButton(header, text="History", width=120, command=self.on_history).pack(side="right", padx=4)

        self.summary_box = ctk.CTkTextbox(self, height=240, fg_color="#0f172a", text_color="#e5e7eb")
        self.summary_box.pack(fill="both", expand=True, padx=8, pady=8)

    def show_summary(self, summary: Dict[str, Any], cfg: Dict[str, Any]) -> None:
        lines = [
            f"Completed: {summary.get('time')}",
            f"Status: {'Success' if summary.get('success') else 'Failed'}",
            f"Message: {summary.get('message')}",
            f"Duration: {summary.get('duration'):.2f}s",
            f"Max airspeed: {summary.get('maxAirspeed'):.2f}",
            f"Max L/D: {summary.get('maxLiftToDrag'):.2f}",
            f"Max pitch rate: {summary.get('maxPitchRate'):.3f}",
            f"Trim solver result: {summary.get('trimResult')}",
            "",
            "Configuration Preview:",
            json.dumps(cfg, indent=2),
        ]
        self.summary_box.delete("1.0", "end")
        self.summary_box.insert("end", "\n".join(lines))
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
                f"Max Airspeed: {item.get('maxAirspeed', 0):.2f}  |  "
                f"Max L/D: {item.get('maxLiftToDrag', 0):.2f}  |  "
                f"Max Pitch Rate: {item.get('maxPitchRate', 0):.3f}  |  "
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

def main() -> None:
    app = FlightSimApp()
    app.mainloop()


if __name__ == "__main__":
    main()
