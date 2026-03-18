import pyodbc

class AircraftData: 
    def __init__(self,SimID):
        self.SimID = SimID

        self.connectID = pyodbc.connect(
            "Driver={SQL Server};"          # Driver for MS SQL
            "Server=localhost\\SQLEXPRESS;" # Instance Name
            "Database=Flight Simulator;"    # Database Name 
            "Trusted_Connection=yes;"     
        )

    def airfoilData(self, columnName):
        cursor = self.connectID.cursor()
        query = f"""
            SELECT AirfoilData.{columnName}
            FROM Simulations
            JOIN Aircraft
                ON Aircraft.AircraftID = Simulations.AircraftID
            JOIN Components
                ON Components.AircraftID = Aircraft.AircraftID
            JOIN AirfoilData
                ON AirfoilData.ComponentID = Components.ComponentID
            WHERE SimID = ?
        """
        cursor.execute(query, (self.SimID,))
        return cursor.fetchval()
    
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
    
    def engineData(self, columnName):
        cursor = self.connectID.cursor()
        query = f"""
            SELECT EngineData.{columnName}
            FROM Simulations
            JOIN Aircraft
                ON Aircraft.AircraftID = Simulations.AircraftID
            JOIN Components
                ON Components.AircraftID = Aircraft.AircraftID
            JOIN EngineData
                ON EngineData.ComponentID = Components.ComponentID
            WHERE SimID = ?
        """
        cursor.execute(query, (self.SimID,))
        return cursor.fetchval()

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
    
    def performanceData(self, columnName):
        cursor = self.connectID.cursor()
        query = f"""
            SELECT PerformanceData.{columnName}
            FROM Simulations
            JOIN Aircraft
                ON Aircraft.AircraftID = Simulations.AircraftID
            JOIN PerformanceData
                ON PerformanceData.AircraftID = Aircraft.AircraftID
            WHERE SimID = ?
        """
        cursor.execute(query, (self.SimID,))
        return cursor.fetchval()


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

    def geometryData(self, columnName):
        cursor = self.connectID.cursor()
        query = f"""
            SELECT Geometry.{columnName}
            FROM Simulations
            JOIN Aircraft
                ON Aircraft.AircraftID = Simulations.AircraftID
            JOIN Geometry
                ON Geometry.AircraftID = Aircraft.AircraftID
            WHERE SimID = ?
        """
        cursor.execute(query, (self.SimID,))
        return cursor.fetchval()

    def length(self):
        return self.geometryData("Length")

    def height(self):
        return self.geometryData("Height")

    def wheelBase(self):
        return self.geometryData("WheelBase")

    def wheelTrack(self):
        return self.geometryData("WheelTrack")
        

hi = AircraftData(1)

print(hi.modelName())