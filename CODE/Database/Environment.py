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

        # CACHE THE DATA - this is to prevent the data being loaded each time a function within this class is called 
        self.data = [] 

        self.load() 

    def load(self):
        cursor = self.connectID.cursor() 

        # SQL Query to get all the environmental data values depending on the EnvironmentID and WeatherID which is defined by SimID 
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
    
   # Recursive Algorithm  
    def interpolationsearch(self,elevation,low,high):

            
        if low>high:
            return False
        
        # Returns the tuple at index low, then returns the first element(elevation value) in that tuple 
        elevation_low = self.data[low][0]
        # Returns the at index high then returns the first element(elevation value) in that tuple 
        elevation_high = self.data[high][0]

        # Error check to ensure the elevation value required does not lie outside the remains of the check
        if elevation <elevation_low or elevation > elevation_high:
            return ("interval",low,high)
           

        # Estimating the position of the element 
        pos = low + int((elevation-elevation_low)*(high-low)/(elevation_high-elevation_low))

        current_elevation = self.data[pos][0] # Estimated elevation  

        if current_elevation == elevation:
            return ("exact",pos) 
        elif elevation < current_elevation:         
            # If the target is smaller than the current estimate, the program begins searching the left side 
            return self.interpolationsearch(elevation,low,pos-1) # Recursive Call 
            # The new high position is set as the current position -1 
        else:
            # If the target is larger than the current estimate, the program begins searching the right side 
            return self.interpolationsearch(elevation,pos+1,high) # Recursive Call 
            # The new low position is set as the current position + 1 
        
    def elevationDetails(self,elevation):

        # If the required elevation lies outside the range of the dataset, then the elevation values are defaulted to 
        if elevation > self.data[len(self.data)-1][0]:
            return self.data[len(self.data)-1]
        if elevation < self.data[0][0]:
            return self.data[0]
        
        index = self.interpolationsearch(elevation,0,len(self.data)-1)


        # If the searching algorithm returns a tuple with first element "interval"
        # It means that interpolation is required as the required elevation is not present in the dataset
        # The function returns the closest elevation values which then can be interpolated 
        if index[0] == "interval": # type: ignore
            l,h = index[1], index[2] # type: ignore
            # ALL elevation details for adjacent rows where the required elevation lies between 
            row1 = self.data[l]
            row2 = self.data[h] # type: ignore
            
            elev1, elev2 = row1[0], row2[1]
            # Calculates the fraction of the interval the required elevation is in 
            fractionofInterval = (elevation - elev1)/(elev2 - elev1)
            
            # New array to store all interpolated values 
            interpolatedRow = [elevation]

            # Calculating the new value for each element by interating through the array 
            for i in range(1, len(row1)):
                value = row1[i] + fractionofInterval * (row2[i]-row1[i])
                interpolatedRow.append(value)
            return interpolatedRow
        else: 
            # If "exact" is stated in the result from the searching function 
            # Then the exact elevation details can be returned 
            return self.data[index[1]] # type: ignore

 
    def temperature(self,elevation):
        temp = self.elevationDetails(elevation)
        return temp[1] 
    
    def pressure(self,elevation):
        pressure = self.elevationDetails(elevation)
        return pressure[2] 
    
    def density(self,elevation):
        density = self.elevationDetails(elevation)
        return (density[3]*1.225) # Multiplying relative density by the actual air density value to get real density 
    
    def visosity(self,elevation):
        visosity = self.elevationDetails(elevation)
        return visosity[4] 
    
    def thermalConductivity(self,elevation):
        conductivity = self.elevationDetails(elevation)
        return conductivity[5] 
    
    def soundSpeed(self,elevation):
        speed = self.elevationDetails(elevation)
        return speed[6] 
    


isa = ISA(2)
#row1,row2 = isa.elevationDetails(2001),isa.elevationDetails(2000)
#print(row1)
#print(row2)

print(isa.density(2888.1))
#print(isa.temperature(50000))
#print(isa.temperature(28000))
#print(isa.thermalConductivity(2000))







        



