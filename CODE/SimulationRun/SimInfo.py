from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import numpy as np

@dataclass
class SimInfo:
    t:float 
    dt: float 

    #Core States 
    trueState = np.ndarray
    stateEstimate = np.ndarray

    #Controls 
    elevator : float = 0.0
    thrust: float = 0.0 

    #Sensors 
    measurement : Optional[np.ndarray] = None 

    #Flags 
    stalled: bool = False 
    converged: bool = False 

    #Simulation Info - Other random data saved for user 
    metaData = Dict[str,Any] = field(default_factory=dict)

    
