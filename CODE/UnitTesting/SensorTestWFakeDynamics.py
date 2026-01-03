import numpy as np
from Sensors.KalmanFilter import Kalman4d



def pitot_airspeed(u, w):
    return np.sqrt(u**2 + w**2)

# Random Values, with u lowered to excentuate disparity 
u_true = 25.0       # forward velocity (LOW)
theta_true = 0.25   # higher pitch angle
z_true = 1000.0

# --- Kalman filter ---
kf = Kalman4d(
    initialStateEstimate=[25, 0, theta_true, z_true],
    initialUncertainityEstimate=np.eye(4),
    processNoiseUncertainity=np.eye(4) * 0.01,
    sensorNoiseUncertainity=np.diag([
        0.2,   
        0.5,
        0.01,
        1.0
    ])
)

dt = 0.1

print("w (m/s) | pitot V (m/s) | estimated u (m/s)")
print("---------------------------------------------")

# Vertical Velocity increasing 
# Creating an array of equally space numbers 
for w_true in np.linspace(0, 35, 10):

    V_pitot = pitot_airspeed(u_true, w_true)

    measurements = [
        V_pitot,     # pitot incorrectly treated as u
        w_true,
        theta_true,
        z_true
    ]

    kf.predict(dt)
    kf.update(measurements)

    estimated_u = kf.stateEstimate[0, 0]

    print('--------')
    print('w m/s (Vertical Speed):', w_true)
    print("Actual Airspeed: ", V_pitot)
    print("Estimated u from Kalman: ", estimated_u)



