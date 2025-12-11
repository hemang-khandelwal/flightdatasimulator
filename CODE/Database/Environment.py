import numpy as np 
import matplotlib.pyplot as plt
import pyodbc

class ISA:
    def __init__(self,SimID):
        self.SimID = SimID

        self.connectID = pyodbc.connect(
            "Driver={SQL Server};"          # Driver for MS SQL
            "Server=localhost\\SQLEXPRESS;" # Instance name
            "Database=Flight Simulator;"         # Database Name
            "Trusted_Connection=yes;"     
        )


        #CACHE THE DATA - this is to prevent the data being loaded each time a function within this class is called 
        self.data = [] 

        self.load() 

    def load(self):
        cursor = self.connectID.cursor() 

        cursor.execute("""
            SELECT 
                ISAData.Elevation,
                ISAData.Temperature,
                ISAData.Pressure,
                ISAData.RelativeDensity,
                ISAData.KinematicViscosity,
                ISAData.ThermalConductivity, 
                ISAData.SpeedOfSound

            FROM 
                Simulations

            JOIN ISAData
                ON ISAData.EnvironmentID = Simulations.EnvironmentID
            AND ISAData.WeatherID  = Simulations.WeatherID

            WHERE Simulations.SimID = ?
            ORDER BY ISAData.Elevation;

        """,(self.SimID))

        self.data = cursor.fetchall() 
        
        #print(data)
        return self.data 
    
    def interpolationsearch(self,elevation,low,high):

        if low>high:
            return False
        
        elevation_low = self.data[low][0]
        elevation_high = self.data[high][0]

        if elevation <elevation_low or elevation > elevation_high:
            return False
        
        pos = low + int((elevation-elevation_low)*(high-low)/(elevation_high-elevation_low))

        current_elevation = self.data[pos][0]

        if current_elevation == elevation:
            return pos 
        
        if elevation < current_elevation:
            return self.interpolationsearch(elevation,low,pos-1)
        else:
            return self.interpolationsearch(elevation,pos+1,high)
        
    def elevationDetails(self,elevation):
        index = self.interpolationsearch(elevation,0,len(self.data)-1)

        if index == False:
            return None 
        
        return self.data[index]
    
    def temperature(self,elevation):
        temp = self.elevationDetails(elevation) # Returns the whole Row with data for each ISA value 
        return temp[1] # type: ignore
    
    def pressure(self,elevation):
        pressure = self.elevationDetails(elevation)
        return pressure[2] #type: ignore
    
    def density(self,elevation):
        density = self.elevationDetails(elevation)
        return density[3] #type: ignore
    
    def visosity(self,elevation):
        visosity = self.elevationDetails(elevation)
        return visosity[4] #type: ignore
    
    def thermalConductivity(self,elevation):
        conductivity = self.elevationDetails(elevation)
        return conductivity[5] #type: ignore
    
    def soundSpeed(self,elevation):
        speed = self.elevationDetails(elevation)
        return speed[6] #type: ignore
    


isa = ISA(1)
#row = isa.elevationDetails(2000)
#print(row)

print(isa.temperature(2000))
print(isa.density(2000))
print(isa.thermalConductivity(2000))







        



