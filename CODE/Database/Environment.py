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

        # self.load() 
    
    def load(self):
        cursor = self.connectID.cursor() 

        cursor.execute("""
            SELECT EnvironmentID 
            FROM Simulations
            Where SimID = ?   
         """),(self.SimID)
        
        environmentID = cursor.fetchall()
        cursor.close()

        cursor.execute("""
            SELECT WeatherID
            FROM Environment
            Where EnvironmentID = ?
        """),(environmentID)
        
        weatherID = cursor.fetchall() 
        cursor.close() 

        


        cursor.execute("""
        SELECT 
            Simulations.EnvironmentID,
            Simulations.Name,
            
            Environment.Name,
            Environment.Lat,
            Environment.Long,
            Environment.WeatherID,
            
            ISAData.Temperature,
            ISAData.Pressure,
            ISAData.RelativeDensity,
            ISAData.KinematicViscosity, 
            ISAData.ThermalConductivity,
            ISAData.SpeedOfSound 
        FROM 
            Simulations,Environment,ISAData 
        JOIN Environment
            ON Simulation.EnvironmentID = Environment.EnvironmentID
        JOIN ISAData
            ON EnvironmentID.EnvironmentID = ISAData.EnvironmentID 
        WHERE 
            Simulations.SimID = ?
            
        """,(self.simID)

        cursor.close() 

        cursor.execute("""
        SELECT 
            ISAData.Temperature,
            ISAData.Pressure,
            ISAData.RelativeDensity,
            ISAData.KinematicViscosity, 
            ISAData.ThermalConductivity,
            ISAData.SpeedOfSound 
                       
        FROM Simulations,Environment,ISAData
                       
        JOIN Simulations 
            ON Simulations.EnvironmentID = Environment.EnvironmentID
        JOIN Simulations 
            ON Simulations.EnvironmentID = ISAData.EnvrionmentID
        JOIN Environment
            ON Environment.WeatherID = ISAData.WeatherID 
        JOIN Environment 
            ON Environment.EnvironmentID = ISAData.EnvironmentID
        
        WHERE 
            Simulations.SimID = ?
            Elevation = ?
        """),(self.SimID)

        data = cursor.fetchall()

        cursor.close() 

        )
