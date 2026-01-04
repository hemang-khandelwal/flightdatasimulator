class Simulation: 
    def __init__(
            self,
            initialState,
            dt,
            aeroModel,
            controls,
            controlsScheduler,
            integrator,
            dynamics,
            forces,
            sensors,
            kalman,
            stall
    ): 
        self.state = initialState
        self.dt = dt 
        self.controls = controls 
        self.controlsScheduler = controlsScheduler
        self.integrator = integrator
        self.dynamics = dynamics 
        self.forces = forces 
        self.sensors = kalman 
        self.stall = stall 


        self.log = []


        def step(self):
            
