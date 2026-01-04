import sys
from pathlib import Path

# Make project modules importable when running this file directly
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Mechanics.Controls import Controls
from Mechanics.Controls import ControlSchedule

controls = Controls("scheduled")
schedule = ControlSchedule()
schedule.addEvent(2,3,0.05,7)
schedule.addEvent(2.9,5,23,102)

controls.schedule = schedule

for t in [1.0, 2.5, 3.5]:
    e = controls.elevator(t)
    thrust = controls.thrust(t)
    print(f"t={t} -> elevator={e}, thrust={thrust}")
