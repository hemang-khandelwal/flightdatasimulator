from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import numpy as np


@dataclass
class SimInfo:
    t: float
    dt: float

    # Core state
    trueState: np.ndarray
    stateEstimate: np.ndarray
    stateDerivative: Optional[np.ndarray] = None

    # Controls
    elevator: float = 0.0
    thrust: float = 0.0

    # Sensors
    measurement: Optional[Any] = None

    # Flags
    stalled: bool = False
    converged: bool = False

    # Simulation Info - Other random data saved for user
    metaData: Dict[str, Any] = field(default_factory=dict)

    
