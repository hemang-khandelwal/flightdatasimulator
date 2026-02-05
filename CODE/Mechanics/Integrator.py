import numpy as np

"""Runge–Kutta 4th-order integrator.

        Args:
            dynamics: object exposing ``stateDerivatives(t, state)``.
            constraint: optional callable(state)->state applied *after*
                the RK4 step (e.g. ground contact). Keeps the math inside
                the derivative clean.
        """
class RK4:
    def __init__(self, dynamics, constraint=None):
   
        self.dynamics = dynamics
        self.constraint = constraint

    def timeStep(self, time, state, dt ):
        f = self.dynamics.stateDerivatives # Stores the derivaties of the SSV (State Space Vector)

        k1 = f(time,state) # Approx for value at the beginning of the interval 
        k2 = f(time+dt/2, state + dt*(k1/2)) # Gives approximation for the midpoint 
        k3 = f(time + dt/2, state + dt*(k2/2)) # A better approximation for the midpoint
        k4 = f(time + dt, state + dt*k3) # Approx for value at the end of the interval

        next_state = state + (dt/6) * (k1 + 2*k2 + 2*k3 + k4) # Weighted average

        # Apply boundary constraint outside the derivative math
        if self.constraint is not None:
            next_state = self.constraint(next_state)

        return next_state


def ground_constraint(state):
    """Clamp to z>=0 (down-positive frame) and stop downward velocity when on ground."""
    u, w, q, theta, x, z = state

    if z <= 0:
        z = 0
        if w >= 0:  # positive w drives further into the ground
            w = 0

    return np.array([u, w, q, theta, x, z], dtype=float)
    


    



    
