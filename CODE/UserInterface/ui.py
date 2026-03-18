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
       # self.history = self._load_history()

        self.container = ctk.CTkFrame(self, fg_color="#0b1220")
        self.container.pack(fill="both", expand=True, padx=12, pady=12)

        self.screens: Dict[str, ctk.CTkFrame] = {}
        #self._build_screens()
        #self.show_screen("menu")


def main() -> None:
    app = FlightSimApp()
    app.mainloop()


if __name__ == "__main__":
    main()
