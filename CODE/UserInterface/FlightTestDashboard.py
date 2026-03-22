from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
import tkinter as tk
import customtkinter as ctk


@dataclass
class TelemetrySnapshot:
    # Time
    t: float

    # State
    u: float
    w: float
    q: float
    theta: float
    x: float
    z: float

    # Derived kinematics
    v: float
    alpha: float
    gamma: float

    # Forces / moments
    lift: float
    drag: float
    moment: float

    # Controls
    thrust: float
    elevator: float

    # Sensors / estimation (optional)
    measured_theta: Optional[float] = None
    measured_z: Optional[float] = None
    est_theta: Optional[float] = None
    est_z: Optional[float] = None

    # Safety
    stalled: bool = False


class TelemetryCollector:
    """
    Responsible for turning the simulation context + domain objects into a single TelemetrySnapshot.
    Keeps derivations out of the dashboard UI so the UI stays dumb and extendable.
    """

    def __init__(self, domain: Dict[str, Any], config: Dict[str, Any]) -> None:
        self._domain = domain
        self._config = config

        self.critical_aoa = None
        if config.get("UseStall") and config.get("criticalAoa") is not None:
            try:
                self.critical_aoa = float(config["criticalAoa"])
            except Exception:
                self.critical_aoa = None

    def collect(self, ctx: Any) -> TelemetrySnapshot:
        state = np.array(ctx.trueState, dtype=float).flatten()
        u = float(state[0]) if state.size > 0 else 0.0
        w = float(state[1]) if state.size > 1 else 0.0
        q = float(state[2]) if state.size > 2 else 0.0
        theta = float(state[3]) if state.size > 3 else 0.0
        x = float(state[4]) if state.size > 4 else 0.0
        z = float(state[5]) if state.size > 5 else 0.0

        v = float(math.hypot(u, w))
        alpha = float(math.atan2(w, u)) if v > 1e-9 else 0.0
        # Consistent with TrimSolver: theta = alpha + gamma
        gamma = float(theta - alpha)

        lift = 0.0
        drag = 0.0
        moment = 0.0
        try:
            env = self._domain.get("environment")
            forces = self._domain.get("forces")
            if env is not None and forces is not None and hasattr(env, "density"):
                rho = float(env.density(z))
                ldm = forces.aeroForces(rho, v, alpha, True)
                lift = float(ldm[0])
                drag = float(ldm[1])
                moment = float(ldm[2])
        except Exception:
            lift, drag, moment = 0.0, 0.0, 0.0

        thrust = float(getattr(ctx, "thrust", 0.0))
        elevator = float(getattr(ctx, "elevator", 0.0))
        stalled = bool(getattr(ctx, "stalled", False))

        measured_theta = None
        measured_z = None
        est_theta = None
        est_z = None

        # Measurement may be dict or array-like (see SimModules)
        m = getattr(ctx, "measurement", None)
        try:
            if isinstance(m, dict):
                measured_theta = float(m.get("theta")) if m.get("theta") is not None else None
                measured_z = float(m.get("z")) if m.get("z") is not None else None
            elif m is not None:
                arr = np.array(m, dtype=float).flatten()
                if arr.size >= 4:
                    measured_theta = float(arr[2])
                    measured_z = float(arr[3])
        except Exception:
            measured_theta, measured_z = None, None

        est = getattr(ctx, "stateEstimate", None)
        try:
            if est is not None:
                arr = np.array(est, dtype=float).flatten()
                if arr.size >= 4:
                    est_theta = float(arr[2])
                    est_z = float(arr[3])
        except Exception:
            est_theta, est_z = None, None

        return TelemetrySnapshot(
            t=float(getattr(ctx, "t", 0.0)),
            u=u,
            w=w,
            q=q,
            theta=theta,
            x=x,
            z=z,
            v=v,
            alpha=alpha,
            gamma=gamma,
            lift=lift,
            drag=drag,
            moment=moment,
            thrust=thrust,
            elevator=elevator,
            measured_theta=measured_theta,
            measured_z=measured_z,
            est_theta=est_theta,
            est_z=est_z,
            stalled=stalled,
        )


class TelemetryPanel(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame) -> None:
        super().__init__(parent, fg_color="#0f172a", corner_radius=12)

        self._rows: Dict[str, ctk.CTkLabel] = {}

        title = ctk.CTkLabel(self, text="Telemetry", font=ctk.CTkFont(size=16, weight="bold"))
        title.pack(anchor="w", padx=10, pady=(10, 6))

        self._add_group("Kinematics", [
            ("Time", "t", "s"),
            ("u", "u", "m/s"),
            ("w", "w", "m/s"),
            ("Airspeed", "v", "m/s"),
            ("theta", "theta", "rad"),
            ("q", "q", "rad/s"),
            ("alpha", "alpha", "deg"),
            ("gamma", "gamma", "deg"),
            ("Altitude", "z", "m"),
            ("Distance", "x", "m"),
        ])
        self._add_group("Aerodynamics", [
            ("Lift", "lift", "N"),
            ("Drag", "drag", "N"),
            ("Moment", "moment", "N m"),
        ])
        self._add_group("Controls", [
            ("Thrust", "thrust", "N"),
            ("Elevator", "elevator", "rad"),
        ])
        self._add_group("Safety", [
            ("Stall", "stalled", ""),
        ])

    def _add_group(self, name: str, rows: Sequence[Tuple[str, str, str]]) -> None:
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=10, pady=(6, 2))
        ctk.CTkLabel(frame, text=name, font=ctk.CTkFont(weight="bold"), text_color="#9ca3af").pack(anchor="w")

        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(fill="x", padx=10)

        for label, key, unit in rows:
            row = ctk.CTkFrame(grid, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=label, width=120, anchor="w", text_color="#9ca3af").pack(side="left")
            value = ctk.CTkLabel(row, text=f"- {unit}".strip(), anchor="w")
            value.pack(side="left", padx=8)
            self._rows[key] = value

    def update(self, snap: TelemetrySnapshot, critical_aoa: Optional[float] = None) -> None:
        def fmt(key: str, value: Any, unit: str = "") -> str:
            if value is None:
                return f"- {unit}".strip()
            if isinstance(value, bool):
                return "STALL" if value else "OK"
            try:
                v = float(value)
            except Exception:
                return f"{value} {unit}".strip()
            return f"{v:.3f} {unit}".strip()

        # degrees for alpha/gamma
        alpha_deg = snap.alpha * 180.0 / math.pi
        gamma_deg = snap.gamma * 180.0 / math.pi

        mapping = {
            "t": (snap.t, "s"),
            "u": (snap.u, "m/s"),
            "w": (snap.w, "m/s"),
            "v": (snap.v, "m/s"),
            "theta": (snap.theta, "rad"),
            "q": (snap.q, "rad/s"),
            "alpha": (alpha_deg, "deg"),
            "gamma": (gamma_deg, "deg"),
            "z": (snap.z, "m"),
            "x": (snap.x, "m"),
            "lift": (snap.lift, "N"),
            "drag": (snap.drag, "N"),
            "moment": (snap.moment, "N m"),
            "thrust": (snap.thrust, "N"),
            "elevator": (snap.elevator, "rad"),
            "stalled": (snap.stalled, ""),
        }

        for key, label in self._rows.items():
            if key not in mapping:
                continue
            v, unit = mapping[key]
            label.configure(text=fmt(key, v, unit))

        # Stall emphasis
        stall_lbl = self._rows.get("stalled")
        if stall_lbl is not None:
            if snap.stalled or (critical_aoa is not None and abs(snap.alpha) >= float(critical_aoa)):
                stall_lbl.configure(text_color="#ef4444")
            else:
                stall_lbl.configure(text_color="#22c55e")


class TimeSeriesChart(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame, title: str, y_label: str) -> None:
        super().__init__(parent, fg_color="#0f172a", corner_radius=12)
        self.title = title
        self.y_label = y_label
        self.series: Dict[str, Dict[str, Any]] = {}
        self.max_points = 800
        self._last_draw = 0.0
        self._draw_hz = 15.0
        self._hline: Optional[float] = None
        self._hline_color = "#ef4444"

        ctk.CTkLabel(self, text=title, font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 0))
        self.canvas = tk.Canvas(self, bg="#0b1220", highlightthickness=0, height=170)
        self.canvas.pack(fill="both", expand=True, padx=10, pady=10)

    def add_series(self, name: str, color: str) -> None:
        self.series[name] = {"color": color, "data": []}  # list[(t,y)]

    def set_hline(self, y: Optional[float], color: str = "#ef4444") -> None:
        self._hline = y
        self._hline_color = color

    def append(self, name: str, t: float, y: Optional[float]) -> None:
        if name not in self.series or y is None:
            return
        data: List[Tuple[float, float]] = self.series[name]["data"]
        data.append((float(t), float(y)))
        if len(data) > self.max_points:
            del data[: len(data) - self.max_points]

    def redraw(self, force: bool = False) -> None:
        now = time.time()
        if not force and (now - self._last_draw) < (1.0 / self._draw_hz):
            return
        self._last_draw = now

        c = self.canvas
        c.delete("all")
        w = c.winfo_width() or 420
        h = c.winfo_height() or 170
        pad_l, pad_r, pad_t, pad_b = 40, 10, 10, 28
        plot_w = max(10, w - pad_l - pad_r)
        plot_h = max(10, h - pad_t - pad_b)

        # Gather extents
        all_pts: List[Tuple[float, float]] = []
        for s in self.series.values():
            all_pts.extend(s["data"])
        if not all_pts:
            c.create_text(pad_l + 10, pad_t + 10, anchor="nw", text="Waiting for data...", fill="#6b7280")
            return

        t_min = min(p[0] for p in all_pts)
        t_max = max(p[0] for p in all_pts)
        y_min = min(p[1] for p in all_pts)
        y_max = max(p[1] for p in all_pts)
        if self._hline is not None:
            y_min = min(y_min, float(self._hline))
            y_max = max(y_max, float(self._hline))

        if t_max == t_min:
            t_max += 1e-6
        if y_max == y_min:
            y_max += 1e-6

        # Axis
        c.create_line(pad_l, pad_t, pad_l, pad_t + plot_h, fill="#374151")
        c.create_line(pad_l, pad_t + plot_h, pad_l + plot_w, pad_t + plot_h, fill="#374151")
        c.create_text(6, pad_t + plot_h / 2, anchor="w", text=self.y_label, fill="#9ca3af", angle=90)
        c.create_text(pad_l + plot_w / 2, h - 6, anchor="s", text="t (s)", fill="#9ca3af")

        # Horizontal line (stall AoA etc)
        if self._hline is not None:
            y = float(self._hline)
            y_px = pad_t + plot_h - ((y - y_min) / (y_max - y_min)) * plot_h
            c.create_line(pad_l, y_px, pad_l + plot_w, y_px, fill=self._hline_color, dash=(4, 3))

        # Series
        for name, s in self.series.items():
            pts = s["data"]
            if len(pts) < 2:
                continue
            xy: List[float] = []
            for t, y in pts:
                x_px = pad_l + ((t - t_min) / (t_max - t_min)) * plot_w
                y_px = pad_t + plot_h - ((y - y_min) / (y_max - y_min)) * plot_h
                xy.extend([x_px, y_px])
            c.create_line(*xy, fill=s["color"], width=2)

        # Tiny legend
        lx = pad_l + 6
        ly = pad_t + 6
        for name, s in self.series.items():
            c.create_rectangle(lx, ly + 4, lx + 10, ly + 14, fill=s["color"], outline=s["color"])
            c.create_text(lx + 14, ly + 9, anchor="w", text=name, fill="#9ca3af")
            ly += 16


class XYChart(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame, title: str, x_label: str, y_label: str) -> None:
        super().__init__(parent, fg_color="#0f172a", corner_radius=12)
        self.title = title
        self.x_label = x_label
        self.y_label = y_label
        self.data: List[Tuple[float, float]] = []
        self.max_points = 1200
        self._last_draw = 0.0
        self._draw_hz = 10.0

        ctk.CTkLabel(self, text=title, font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 0))
        self.canvas = tk.Canvas(self, bg="#0b1220", highlightthickness=0, height=170)
        self.canvas.pack(fill="both", expand=True, padx=10, pady=10)

    def append(self, x: float, y: float) -> None:
        self.data.append((float(x), float(y)))
        if len(self.data) > self.max_points:
            del self.data[: len(self.data) - self.max_points]

    def redraw(self, force: bool = False) -> None:
        now = time.time()
        if not force and (now - self._last_draw) < (1.0 / self._draw_hz):
            return
        self._last_draw = now

        c = self.canvas
        c.delete("all")
        w = c.winfo_width() or 420
        h = c.winfo_height() or 170
        pad_l, pad_r, pad_t, pad_b = 40, 10, 10, 28
        plot_w = max(10, w - pad_l - pad_r)
        plot_h = max(10, h - pad_t - pad_b)

        if len(self.data) < 2:
            c.create_text(pad_l + 10, pad_t + 10, anchor="nw", text="Waiting for data...", fill="#6b7280")
            return

        xs = [p[0] for p in self.data]
        ys = [p[1] for p in self.data]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        if x_max == x_min:
            x_max += 1e-6
        if y_max == y_min:
            y_max += 1e-6

        c.create_line(pad_l, pad_t, pad_l, pad_t + plot_h, fill="#374151")
        c.create_line(pad_l, pad_t + plot_h, pad_l + plot_w, pad_t + plot_h, fill="#374151")
        c.create_text(6, pad_t + plot_h / 2, anchor="w", text=self.y_label, fill="#9ca3af", angle=90)
        c.create_text(pad_l + plot_w / 2, h - 6, anchor="s", text=self.x_label, fill="#9ca3af")

        xy: List[float] = []
        for x, y in self.data:
            x_px = pad_l + ((x - x_min) / (x_max - x_min)) * plot_w
            y_px = pad_t + plot_h - ((y - y_min) / (y_max - y_min)) * plot_h
            xy.extend([x_px, y_px])
        c.create_line(*xy, fill="#60a5fa", width=2)
        c.create_oval(xy[-2] - 3, xy[-1] - 3, xy[-2] + 3, xy[-1] + 3, fill="#22c55e", outline="")


class EventLog(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame) -> None:
        super().__init__(parent, fg_color="#0f172a", corner_radius=12)
        ctk.CTkLabel(self, text="Event Log", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(8, 0))
        self.box = ctk.CTkTextbox(self, height=220, fg_color="#0b1220", text_color="#e5e7eb")
        self.box.pack(fill="both", expand=True, padx=10, pady=10)
        self.box.configure(state="disabled")

    def log(self, message: str) -> None:
        self.box.configure(state="normal")
        self.box.insert("end", message.rstrip() + "\n")
        self.box.see("end")
        self.box.configure(state="disabled")


class FlightTestDashboard(ctk.CTkFrame):
    def __init__(
        self,
        parent: ctk.CTkFrame,
        on_abort: Callable[[], None],
        on_pause: Optional[Callable[[], None]] = None,
        on_export: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(parent, fg_color="#0b1220")
        self.on_abort = on_abort
        self.on_pause = on_pause
        self.on_export = on_export

        self.critical_aoa: Optional[float] = None

        header = ctk.CTkFrame(self, fg_color="#0b1220")
        header.pack(fill="x", padx=10, pady=8)
        ctk.CTkLabel(header, text="Flight-Test Live Dashboard", font=ctk.CTkFont(size=20, weight="bold")).pack(
            side="left"
        )

        btns = ctk.CTkFrame(header, fg_color="transparent")
        btns.pack(side="right")
        if on_export is not None:
            ctk.CTkButton(btns, text="Export", width=90, command=on_export).pack(side="left", padx=6)
        if on_pause is not None:
            ctk.CTkButton(btns, text="Pause/Resume", width=130, command=on_pause).pack(side="left", padx=6)
        ctk.CTkButton(btns, text="Abort", fg_color="#ef4444", width=90, command=on_abort).pack(side="left", padx=6)

        body = ctk.CTkFrame(self, fg_color="#0b1220")
        body.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # 3-region layout
        self.left = TelemetryPanel(body)
        self.left.pack(side="left", fill="y", padx=(0, 10))

        self.center = ctk.CTkFrame(body, fg_color="transparent")
        self.center.pack(side="left", fill="both", expand=True)

        self.right = ctk.CTkFrame(body, fg_color="transparent")
        self.right.pack(side="right", fill="y", padx=(10, 0))

        # Center grid (2x2 main graphs)
        self.center.grid_columnconfigure(0, weight=1)
        self.center.grid_columnconfigure(1, weight=1)
        self.center.grid_rowconfigure(0, weight=1)
        self.center.grid_rowconfigure(1, weight=1)

        self.chart_aoa = TimeSeriesChart(self.center, "Angle of Attack vs Time", "alpha (deg)")
        self.chart_aoa.add_series("alpha", "#60a5fa")
        self.chart_pitch = TimeSeriesChart(self.center, "Pitch Response", "theta/q")
        self.chart_pitch.add_series("theta", "#fbbf24")
        self.chart_pitch.add_series("q", "#a78bfa")
        self.chart_forces = TimeSeriesChart(self.center, "Lift and Drag vs Time", "N")
        self.chart_forces.add_series("Lift", "#22c55e")
        self.chart_forces.add_series("Drag", "#ef4444")
        self.chart_traj = XYChart(self.center, "Trajectory", "x (m)", "z (m)")

        self.chart_aoa.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        self.chart_pitch.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)
        self.chart_traj.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
        self.chart_forces.grid(row=1, column=1, sticky="nsew", padx=6, pady=6)

        # Right side analytics
        self.chart_elevator = TimeSeriesChart(self.right, "Elevator Input vs Time", "rad")
        self.chart_elevator.add_series("elevator", "#93c5fd")
        self.chart_sensor = TimeSeriesChart(self.right, "True vs Measured vs Filtered (theta)", "rad")
        self.chart_sensor.add_series("true", "#fbbf24")
        self.chart_sensor.add_series("measured", "#94a3b8")
        self.chart_sensor.add_series("filtered", "#22c55e")

        self.chart_elevator.pack(fill="x", pady=(0, 10))
        self.chart_sensor.pack(fill="x", pady=(0, 10))
        self.events = EventLog(self.right)
        self.events.pack(fill="both", expand=True)

    def reset(self, critical_aoa: Optional[float] = None) -> None:
        self.critical_aoa = critical_aoa
        self.chart_aoa.set_hline(None)
        if critical_aoa is not None:
            self.chart_aoa.set_hline(float(critical_aoa) * 180.0 / math.pi, color="#ef4444")

        for chart in [self.chart_aoa, self.chart_pitch, self.chart_forces, self.chart_elevator, self.chart_sensor]:
            for s in chart.series.values():
                s["data"].clear()
            chart.redraw(force=True)
        self.chart_traj.data.clear()
        self.chart_traj.redraw(force=True)

        self.events.log("Simulation started")

    def log_event(self, message: str) -> None:
        self.events.log(message)

    def update(self, snap: TelemetrySnapshot) -> None:
        self.left.update(snap, critical_aoa=self.critical_aoa)

        alpha_deg = snap.alpha * 180.0 / math.pi
        self.chart_aoa.append("alpha", snap.t, alpha_deg)
        self.chart_pitch.append("theta", snap.t, snap.theta)
        self.chart_pitch.append("q", snap.t, snap.q)
        self.chart_elevator.append("elevator", snap.t, snap.elevator)
        self.chart_forces.append("Lift", snap.t, snap.lift)
        self.chart_forces.append("Drag", snap.t, snap.drag)
        self.chart_traj.append(snap.x, snap.z)

        # Sensor chart (theta)
        self.chart_sensor.append("true", snap.t, snap.theta)
        self.chart_sensor.append("measured", snap.t, snap.measured_theta)
        self.chart_sensor.append("filtered", snap.t, snap.est_theta)

        # Redraw throttled inside chart classes
        self.chart_aoa.redraw()
        self.chart_pitch.redraw()
        self.chart_elevator.redraw()
        self.chart_forces.redraw()
        self.chart_sensor.redraw()
        self.chart_traj.redraw()

