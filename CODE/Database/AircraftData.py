import pyodbc

class AircraftData:
    def __init__(self, SimID=None, aircraft_id=None):
        self.SimID = SimID
        self.aircraft_id = aircraft_id

        self.connectID = pyodbc.connect(
            "Driver={SQL Server};"          # Driver for MS SQL
            "Server=localhost\\SQLEXPRESS;" # Instance Name
            "Database=Flight Simulator;"    # Database Name 
            "Trusted_Connection=yes;"     
        )

    @classmethod
    def from_aircraft_id(cls, aircraft_id):
        return cls(SimID=None, aircraft_id=aircraft_id)

    @classmethod
    def from_sim_id(cls, sim_id):
        return cls(SimID=sim_id, aircraft_id=None)

    def _safe_execute(self, query, params):
        cursor = self.connectID.cursor()
        cursor.execute(query, params)
        result = cursor.fetchone()
        if result is None:
            return None
        return result[0]

    def _airfoil_query(self, columnName):
        if self.aircraft_id is not None:
            query = f"""
            SELECT AirfoilData.{columnName}
            FROM Components
            JOIN AirfoilData
                ON AirfoilData.ComponentID = Components.ComponentID
            WHERE Components.AircraftID = ?
            """
            return self._safe_execute(query, (self.aircraft_id,))

        query = f"""
            SELECT AirfoilData.{columnName}
            FROM Simulations
            JOIN Aircraft
                ON Aircraft.AircraftID = Simulations.AircraftID
            JOIN Components
                ON Components.AircraftID = Aircraft.AircraftID
            JOIN AirfoilData
                ON AirfoilData.ComponentID = Components.ComponentID
            WHERE Simulations.SimID = ?
        """
        return self._safe_execute(query, (self.SimID,))

    def airfoilData(self, columnName):
        return self._airfoil_query(columnName)

    def wingArea(self):
        return self.airfoilData("WingArea")
  
    def aerodynamicChord(self):
        return self.airfoilData("AerodynamicChord")

    def wingAirfoil(self):
        return self.airfoilData("WingAirfoil")

    def horizontalAirfoilAtRoot(self):
        return self.airfoilData("HorizontalAirfoilAtRoot")

    def horizontalAirfoilAtTip(self):
        return self.airfoilData("HorizontalAirfoilAtTip")

    def aileronsDeflectionLimit(self):
        return self.airfoilData("AileronsDeflectionLimit")

    def aileronsArea(self):
        return self.airfoilData("AileronsArea")

    def elevatorDeflectionLimitMax(self):
        return self.airfoilData("ElevatorDeflectionLimitMax")

    def elevatorDeflectionLimitMin(self):
        return self.airfoilData("ElevatorDeflectionLimitMin")

    def elevatorArea(self):
        return self.airfoilData("ElevatorArea")

    def rudderDeflectionLimit(self):
        return self.airfoilData("RudderDeflectionLimit")

    def flapsArea(self):
        return self.airfoilData("FlapsArea")

    def flapsDeflectionLimit(self):
        return self.airfoilData("FlapsDeflectionLimit")
    
    def _engine_query(self, columnName):
        if self.aircraft_id is not None:
            query = f"""
            SELECT EngineData.{columnName}
            FROM Components
            JOIN EngineData
                ON EngineData.ComponentID = Components.ComponentID
            WHERE Components.AircraftID = ?
            """
            return self._safe_execute(query, (self.aircraft_id,))

        query = f"""
            SELECT EngineData.{columnName}
            FROM Simulations
            JOIN Aircraft
                ON Aircraft.AircraftID = Simulations.AircraftID
            JOIN Components
                ON Components.AircraftID = Aircraft.AircraftID
            JOIN EngineData
                ON EngineData.ComponentID = Components.ComponentID
            WHERE Simulations.SimID = ?
        """
        return self._safe_execute(query, (self.SimID,))

    def engineData(self, columnName):
        return self._engine_query(columnName)

    def modelName(self):
        return self.engineData("ModelName")

    def ratedPower(self):
        return self.engineData("RatedPower")

    def displacement(self):
        return self.engineData("Displacement")

    def engineHeight(self):
        return self.engineData("Height")

    def engineWidth(self):
        return self.engineData("Width")

    def engineLength(self):
        return self.engineData("Length")

    def specificFuelConsumption(self):
        return self.engineData("SpecificFuelConsumption")

    def noOfBlades(self):
        return self.engineData("NoOfBlades")

    def propellerDiameter(self):
        return self.engineData("PropellerDiameter")
    
    def _performance_query(self, columnName):
        perf_tables = ["PerformanceData", "Performance", "Performance_Data"]

        if self.aircraft_id is not None:
            for table in perf_tables:
                try:
                    query = f"""
                    SELECT [{table}].{columnName}
                    FROM [{table}]
                    WHERE [{table}].AircraftID = ?
                    """
                    return self._safe_execute(query, (self.aircraft_id,))
                except pyodbc.ProgrammingError:
                    continue
            return None

        for table in perf_tables:
            try:
                query = f"""
                    SELECT [{table}].{columnName}
                    FROM Simulations
                    JOIN Aircraft
                        ON Aircraft.AircraftID = Simulations.AircraftID
                    JOIN [{table}]
                        ON [{table}].AircraftID = Aircraft.AircraftID
                    WHERE Simulations.SimID = ?
                """
                return self._safe_execute(query, (self.SimID,))
            except pyodbc.ProgrammingError:
                continue
        return None

    def performanceData(self, columnName):
        return self._performance_query(columnName)


    def normalMaxTakeOffWeight(self):
        return self.performanceData("NormalMaxTakeOffWeight")

    def utilityMaxTakeOffWeight(self):
        return self.performanceData("UtilityMaxTakeOffWeight")

    def stallSpeed(self):
        return self.performanceData("StallSpeed")

    def cruiseSpeed(self):
        return self.performanceData("CruiseSpeed")

    def seaLevelMaxSpeed(self):
        return self.performanceData("SeaLevelMaxSpeed")

    def neverExceedSpeed(self):
        return self.performanceData("NeverExceedSpeed")

    def serviceCeiling(self):
        return self.performanceData("ServiceCeiling")

    def takeOffRun(self):
        return self.performanceData("TakeOffRun")

    def landingRun(self):
        return self.performanceData("LandingRun")

    def eightyRange(self):
        return self.performanceData("EightyRange")

    def sixtyRange(self):
        return self.performanceData("SixtyRange")

    def _geometry_query(self, columnName):
        if self.aircraft_id is not None:
            query = f"""
            SELECT Geometry.{columnName}
            FROM Geometry
            WHERE Geometry.AircraftID = ?
            """
            return self._safe_execute(query, (self.aircraft_id,))

        query = f"""
            SELECT Geometry.{columnName}
            FROM Simulations
            JOIN Aircraft
                ON Aircraft.AircraftID = Simulations.AircraftID
            JOIN Geometry
                ON Geometry.AircraftID = Aircraft.AircraftID
            WHERE Simulations.SimID = ?
        """
        return self._safe_execute(query, (self.SimID,))

    def geometryData(self, columnName):
        return self._geometry_query(columnName)

    def length(self):
        return self.geometryData("Length")

    def height(self):
        return self.geometryData("Height")

    def wheelBase(self):
        return self.geometryData("WheelBase")

    def wheelTrack(self):
        return self.geometryData("WheelTrack")

