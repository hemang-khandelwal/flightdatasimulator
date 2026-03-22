# Flight Simulator Database Schema

## Database Connection Details
- **Database Name:** Flight Simulator
- **Server:** localhost\SQLEXPRESS
- **Connection Type:** SQL Server with Windows Authentication (pyodbc)

---

## Tables and Columns

### 1. **Simulations**
Core table that links simulations to aircraft, environment, and weather data.

| Column | Type | Description |
|--------|------|-------------|
| SimID | INT (Primary Key) | Unique simulation identifier |
| VersionID | INT | Version number |
| Name | VARCHAR | Simulation name |
| Description | VARCHAR | Simulation description |
| AircraftID | INT (FK) | References Aircraft.AircraftID |
| EnvironmentID | INT (FK) | References Environment.EnvironmentID |
| WeatherID | INT (FK) | Weather condition identifier |

**Usage:** Stores simulation metadata and links to aircraft, environmental conditions, and weather.

---

### 2. **Aircraft**
Master table for aircraft types.

| Column | Type | Description |
|--------|------|-------------|
| AircraftID | INT (Primary Key) | Unique aircraft identifier |
| Name | VARCHAR | Aircraft name (e.g., "Cessna 172") |
| Manufacturer | VARCHAR | Aircraft manufacturer (inferred) |

**Usage:** References aircraft used in simulations. Other tables use AircraftID as foreign key to link aerodynamic, performance, and geometric data to specific aircraft.

---

### 3. **Components**
Stores components (wings, engines, control surfaces) for each aircraft.

| Column | Type | Description |
|--------|------|-------------|
| ComponentID | INT (Primary Key) | Unique component identifier |
| AircraftID | INT (FK) | References Aircraft.AircraftID |

**Usage:** Acts as bridge table linking aircraft to their airfoil and engine data.

---

### 4. **AirfoilData**
Contains aerodynamic surface properties (wings, control surfaces).

| Column | Type | Description |
|--------|------|-------------|
| ComponentID | INT (Primary Key/FK) | References Components.ComponentID |
| WingArea | FLOAT | Wing planform area (m²) |
| AerodynamicChord | FLOAT | Mean aerodynamic chord (m) |
| WingAirfoil | VARCHAR | Wing airfoil designation |
| HorizontalAirfoilAtRoot | VARCHAR | Horizontal stabilizer airfoil at root |
| HorizontalAirfoilAtTip | VARCHAR | Horizontal stabilizer airfoil at tip |
| AileronsDeflectionLimit | FLOAT | Max aileron deflection (degrees) |
| AileronsArea | FLOAT | Aileron surface area (m²) |
| ElevatorDeflectionLimitMax | FLOAT | Max elevator deflection (degrees) |
| ElevatorDeflectionLimitMin | FLOAT | Min elevator deflection (degrees) |
| ElevatorArea | FLOAT | Elevator surface area (m²) |
| RudderDeflectionLimit | FLOAT | Max rudder deflection (degrees) |
| FlapsArea | FLOAT | Flap surface area (m²) |
| FlapsDeflectionLimit | FLOAT | Max flap deflection (degrees) |

**Usage:** Stores all aerodynamic surface parameters for lift, drag, and moment calculations.

---

### 5. **EngineData**
Contains engine and propeller specifications.

| Column | Type | Description |
|--------|------|-------------|
| ComponentID | INT (Primary Key/FK) | References Components.ComponentID |
| ModelName | VARCHAR | Engine model designation |
| RatedPower | FLOAT | Maximum rated power (kW) |
| Displacement | FLOAT | Engine displacement (cc) |
| Height | FLOAT | Engine height (m) |
| Width | FLOAT | Engine width (m) |
| Length | FLOAT | Engine length (m) |
| SpecificFuelConsumption | FLOAT | Fuel consumption rate (kg/kW/h) |
| NoOfBlades | INT | Number of propeller blades |
| PropellerDiameter | FLOAT | Propeller diameter (m) |

**Usage:** Defines engine performance characteristics and physical dimensions.

---

### 6. **PerformanceData**
Contains aircraft performance envelopes and limits.

| Column | Type | Description |
|--------|------|-------------|
| AircraftID | INT (Primary Key/FK) | References Aircraft.AircraftID |
| NormalMaxTakeOffWeight | FLOAT | MTOW for normal category (kg) |
| UtilityMaxTakeOffWeight | FLOAT | MTOW for utility category (kg) |
| StallSpeed | FLOAT | Stall speed (knots) |
| CruiseSpeed | FLOAT | Optimal cruise speed (knots) |
| SeaLevelMaxSpeed | FLOAT | Max speed at sea level (knots) |
| NeverExceedSpeed | FLOAT | VNE - never exceed speed (knots) |
| ServiceCeiling | FLOAT | Service ceiling altitude (feet) |
| TakeOffRun | FLOAT | Takeoff distance required (m) |
| LandingRun | FLOAT | Landing distance required (m) |
| EightyRange | FLOAT | Range at 80% power (nautical miles) |
| SixtyRange | FLOAT | Range at 60% power (nautical miles) |

**Usage:** Stores aircraft performance limitations and operating envelopes critical for flight dynamics simulation.

---

### 7. **Geometry**
Contains aircraft physical dimensions and reference points.

| Column | Type | Description |
|--------|------|-------------|
| AircraftID | INT (Primary Key/FK) | References Aircraft.AircraftID |
| Length | FLOAT | Fuselage length (m) |
| Height | FLOAT | Fuselage height (m) |
| WheelBase | FLOAT | Distance between main wheels (m) |
| WheelTrack | FLOAT | Distance between left/right wheels (m) |

**Usage:** Provides geometric properties needed for ground handling and landing simulation.

---

### 8. **AeroCoefficients**
Stores aerodynamic coefficients (lift, drag, moment) vs. angle of attack by flight regime.

| Column | Type | Description |
|--------|------|-------------|
| AircraftID | INT (FK) | References Aircraft.AircraftID |
| RegimeID | INT | Flight regime identifier (e.g., 1=clean, 2=landing gear down, etc.) |
| Alpha | FLOAT | Angle of attack (degrees) |
| CL | FLOAT | Lift coefficient |
| CD | FLOAT | Drag coefficient |
| CM | FLOAT | Moment (pitch) coefficient |

**PK:** Composite key of (AircraftID, RegimeID, Alpha)

**Usage:** Provides lookup tables for aerodynamic coefficients. Used by BaseAeroModel class for polynomial regression fitting.

---

### 9. **ISAData**
International Standard Atmosphere data - environmental conditions.

| Column | Type | Description |
|--------|------|-------------|
| EnvironmentID | INT (FK) | References Environment.EnvironmentID |
| WeatherID | INT (FK) | Weather condition identifier |
| Elevation | FLOAT | Altitude above sea level (feet) |
| Temperature | FLOAT | Air temperature (°C) |
| Pressure | FLOAT | Static pressure (Pa or mb) |
| RelativeDensity | FLOAT | Air density relative to sea level |
| KinematicViscosity | FLOAT | Kinematic viscosity (m²/s) |
| ThermalConductivity | FLOAT | Thermal conductivity (W/m·K) |
| SpeedOfSound | FLOAT | Speed of sound (m/s) |

**Usage:** Stores atmospheric properties at different elevations and weather conditions. Critical for aerodynamic force calculations which are density-dependent.

---

### 10. **Environment**
Defines geographical and weather context for simulations.

| Column | Type | Description |
|--------|------|-------------|
| EnvironmentID | INT (Primary Key) | Unique environment identifier |
| Name | VARCHAR | Location name |
| Lat | FLOAT | Latitude |
| Long | FLOAT | Longitude |
| WeatherID | INT (FK) | Associated weather condition |

**Usage:** Links simulations to geographical locations and weather patterns.

---

### 11. **SensorNoise**
Stores sensor noise configuration for simulation fidelity.

| Column | Type | Description |
|--------|------|-------------|
| NoiseSimID | INT (Primary Key) | Unique noise simulation identifier |
| Enabled | INT | Boolean flag (0=disabled, 1=enabled) |
| StdDev | FLOAT | Standard deviation of noise (m/s or m) |
| Frequency | FLOAT | Sampling frequency (Hz) |

**Usage:** Configures sensor noise characteristics for Kalman filter testing.

---

### 12. **TrimSolver**
Stores trim solver configuration and convergence parameters.

| Column | Type | Description |
|--------|------|-------------|
| TrimSolverID | INT (Primary Key) | Unique trim solver configuration ID |
| Tolerance | FLOAT | Convergence tolerance (e.g., 1e-6) |
| Iterations | INT | Maximum iterations allowed |

**Usage:** Stores parameters for finding equilibrium flight conditions (trim).

---

## Key Query Patterns

### Get Aircraft Specifications
```sql
SELECT 
    a.AircraftID, a.Name,
    af.WingArea, af.AerodynamicChord,
    e.ModelName, e.RatedPower,
    p.StallSpeed, p.CruiseSpeed, p.NeverExceedSpeed,
    g.Length, g.Height
FROM Aircraft a
JOIN Components c ON c.AircraftID = a.AircraftID
JOIN AirfoilData af ON af.ComponentID = c.ComponentID
JOIN EngineData e ON e.ComponentID = c.ComponentID
JOIN PerformanceData p ON p.AircraftID = a.AircraftID
JOIN Geometry g ON g.AircraftID = a.AircraftID
WHERE a.AircraftID = ?
```

### Get Aerodynamic Coefficients for a Flight Regime
```sql
SELECT Alpha, CL, CD, CM
FROM AeroCoefficients
WHERE AircraftID = ? AND RegimeID = ?
ORDER BY Alpha
```

### Get Environmental Data for Simulation
```sql
SELECT 
    s.SimID, s.Name,
    e.Name as Location,
    isa.Elevation, isa.Temperature, isa.Pressure, 
    isa.RelativeDensity, isa.KinematicViscosity, isa.SpeedOfSound
FROM Simulations s
JOIN Environment e ON e.EnvironmentID = s.EnvironmentID
JOIN ISAData isa ON isa.EnvironmentID = s.EnvironmentID 
    AND isa.WeatherID = s.WeatherID
WHERE s.SimID = ?
ORDER BY isa.Elevation
```

---

## Data Classes Using This Schema

### [AircraftData.py](CODE/Database/AircraftData.py)
Provides object-oriented access to aircraft specifications:
- `airfoilData()` - Queries AirfoilData via Components
- `engineData()` - Queries EngineData via Components
- `performanceData()` - Queries PerformanceData
- `geometryData()` - Queries Geometry

### [BaseAeroModel.py](CODE/Database/BaseAeroModel.py)
Loads and interpolates aerodynamic coefficients:
- `loadData()` - Reads from AeroCoefficients table
- Performs polynomial regression on CL, CD, CM coefficients

### [Environment.py](CODE/Database/Environment.py)
Provides atmospheric data access:
- `load()` - Queries ISAData for elevation-based interpolation
- Returns temperature, pressure, density, viscosity, speed of sound

### [SimulationDatabase](CODE/UserInterface/App.py)
Saves simulation configuration and results:
- `saveSim()` - Inserts into Simulations
- `_insert_sensor_noise()` - Inserts into SensorNoise
- `_insert_trim_solver()` - Inserts into TrimSolver

---

## Notes
- All foreign key relationships appear to be implicit (not explicitly enforced constraints visible in code)
- Data is queried using pyodbc with parameterized queries
- Aircraft data is accessed either by AircraftID or SimID
- ISAData interpolation is done in code using the elevation column as search key
- The `Components` table acts as a junction table between Aircraft and component-specific data (Airfoil, Engine)
