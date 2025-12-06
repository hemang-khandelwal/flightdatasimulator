import numpy as np 
import matplotlib.pyplot as plt
import pyodbc

class AeroModel: 
    def __init__(self,aircraftID,regimeID,degree):
        self.connectID = pyodbc.connect(
                "Driver={SQL Server};"          # Driver for MS SQL
                "Server=localhost\\SQLEXPRESS;" # Instance Name
                "Database=Flight Simulator;"         # Database Name 
                "Trusted_Connection=yes;"     
        )
        self.aircraftID = aircraftID
        self.regimeID = regimeID 
        self.degree = degree 
        self.coeff = None 

        ## LOAD DATA 

        self.aoa, self.cl, self.cd, self.cm = [], [], [], []
        self.residuals_cl, self.residuals_cd, self.residuals_cm = [], [], []

        # fill arrays
        self.loadData()
        ### CACHE ##### 
        ## Calculate the coefficients once only for each coefficient 

        self.a_cl = self.regression("cl")
        self.a_cd = self.regression("cd")
        self.a_cm = self.regression("cm")


        self.residualCL = []
        self.residualCD = [] 
        self.residualCM = []

        for index in range(len(self.aoa)):
            aoa_value = self.aoa[index]
            actual_value = self.cl[index]

            predicted_value = self.coeffCalc(aoa_value, self.a_cl)
            residual_value = actual_value - predicted_value

            self.residualCL.append(residual_value)

        for index in range(len(self.aoa)):
            aoa_value = self.aoa[index]
            actual_value = self.cd[index]

            predicted_value = self.coeffCalc(aoa_value, self.a_cd)
            residual_value = actual_value - predicted_value

            self.residualCD.append(residual_value)

        for index in range(len(self.aoa)):
            aoa_value = self.aoa[index]
            actual_value = self.cm[index]

            predicted_value = self.coeffCalc(aoa_value, self.a_cm)
            residual_value = actual_value - predicted_value

            self.residualCM.append(residual_value)
   



    def loadData(self): 
        cursor = self.connectID.cursor() 

        cursor.execute("""
        SELECT Alpha,CL,CD,CM
        FROM AeroCoefficients 
        WHERE AircraftID = ? AND RegimeID = ?
        ORDER BY Alpha
        """, (self.aircraftID, self.regimeID))

        self.aoa.clear()
        self.cl.clear()
        self.cd.clear()
        self.cm.clear()

        for row in cursor:
            self.aoa.append(row[0])
            self.cl.append(row[1])
            self.cd.append(row[2])
            self.cm.append(row[3])

        cursor.close()

        return self.aoa, self.cl, self.cd, self.cm 
    
    def matrixBuilder(self,coeff):
        poly = np.array([])
        ## Makes the Vandermonde Matrix of X values by having each Aoa value to a certain power 
        for i in range (0,len(self.aoa)):
            for b in range (0,self.degree):
                #print(aoa[i])
                number = self.aoa[i] ** b
                #print(number)
                poly = np.append(poly,number)
        
        ## Split the big array into Matrix Form 

        rows = len(self.aoa)
        cols = self.degree 
        self.vanMatrix = [] 
        
        for c in range (rows):
            row = []
            for d in range(cols):
                index = c * cols + d 
                row.append(poly[index]) ## Splitting the Long Flat 1D List into multiple seperate arrays 

            self.vanMatrix.append(row)
            
        self.vanMatrix = [[float(value) for value in row] for row in self.vanMatrix] # Making the mutliple arrays into Matrix Form 

        self.yVals = []

        coeffVal = getattr(self, coeff)

        for value in coeffVal:
            self.yVals.append([value])
        
        return self.vanMatrix , self.yVals

    def transpose(self, matrix):
        rows = len(matrix)
        cols = len(matrix[0])
        transposedMatrix = [[0 for _ in range(rows)] for _ in range(cols)]
        for i in range(rows):
            for j in range(cols):
                transposedMatrix[j][i] = matrix[i][j]

        return transposedMatrix
    

    def regression(self,coeff):
        print("REGRESSION CALLED with degree =", self.degree)

        #self.loadData() # Loads the data from MS SQL 
        matrix, yvals = self.matrixBuilder(coeff) # Builds matrix for Aoa Values and AeroCoeff
        result = self.transpose(matrix)

        #print(result)
        X = np.array(matrix)
        Xt = np.array(result)
        y = np.array(yvals)
        XXt = Xt @ X
        inv = np.linalg.inv(XXt)
        xty = Xt @ y 
        a = inv @ xty 
        
        return a # returns the regression coefficients 
    
    # Calculates the Value of the Coefficient 
    # This doesn't call the regression function each time which increases computational overhead 
    def coeffCalc(self,angle,coeffvector):
        total = 0 
        for power, coef in enumerate(coeffvector.flatten()):
            total += coef * (angle**power)
        return float(total)
  
    # Returns the final value after calculation by the coeffCalc Function 
    def regressionPredict(self,angle,coeff): 
        if coeff == "cl":
            return self.coeffCalc(angle,self.a_cl)
        elif coeff == "cd":
            return self.coeffCalc(angle,self.a_cd)
        else:
            return self.coeffCalc(angle,self.a_cm)

    def residualcalc(self,angle,coeff):
        if coeff == "cl":
            residual_list = self.residualCL
        elif coeff == "cd":
            residual_list = self.residualCD
        else:
            residual_list = self.residualCM

        index = self.aoa.index(angle)

        return residual_list[index]


        
               
    #def residualcalc(self, angle ,coeff):
       # residuals = []
        #coeffVal = getattr(self, coeff)
        #for ind,number in enumerate(self.aoa): 
         #   error = coeffVal[ind] - self.regressionPredict(number,coeff)
          #  residuals.append(error)
        #return residuals[self.aoa.index(angle)] # returns the specific residual for a specific aoa 
    
    def errorcorrect(self,value,coeff): 
        for y in range(len(self.aoa)-1):

            ## Checking which two values the desired angle of attack is between 

            a1,a2 = self.aoa[y], self.aoa[y+1] 
            r1= self.residualcalc(a1, coeff)
            r2 = self.residualcalc(a2,coeff)

            if a1 <= value <= a2: 
                ans = r1 + ((r2 - r1) / (a2 - a1)) * (value - a1)
                return ans 
            
        if value < self.aoa[0]:
            return self.residualcalc(self.aoa[0], coeff)
        else:
            return self.residualcalc(self.aoa[-1], coeff)
        
    def aeroval(self, angle, coefficient: str) -> float:
        reg_val = self.regressionPredict(angle,coefficient)
        correction = self.errorcorrect(angle,coefficient)
        final_val = reg_val + correction 

        return final_val
    
    def refreshCache(self):
        # Reload data from database
        self.loadData()

        # Recalculate regression for new degree
        self.a_cl = self.regression("cl")
        self.a_cd = self.regression("cd")
        self.a_cm = self.regression("cm")

        # Recalculate residuals
        self.residualCL = []
        self.residualCD = []
        self.residualCM = []

        for index in range(len(self.aoa)):
            aoa_val = self.aoa[index]

            # CL residual
            pred_cl = self.coeffCalc(aoa_val, self.a_cl)
            self.residualCL.append(self.cl[index] - pred_cl)

            # CD residual
            pred_cd = self.coeffCalc(aoa_val, self.a_cd)
            self.residualCD.append(self.cd[index] - pred_cd)

            # CM residual
            pred_cm = self.coeffCalc(aoa_val, self.a_cm)
            self.residualCM.append(self.cm[index] - pred_cm)

        print("Cache refreshed for degree:", self.degree)

    def plotHybridFit(self, coeff):

        # --- Extract AoA and chosen coefficient
        aoa = np.array(self.aoa)
        coeffVal = np.array(getattr(self, coeff))  
        
        #--- Compute regression + corrected values at data points ---
        regression_at_points = [self.regressionPredict(alpha, coeff) for alpha in aoa]
        corrected_at_points = [
            self.regressionPredict(alpha, coeff) + self.errorcorrect(alpha, coeff)
            for alpha in aoa
        ]

        # --- Compute residuals (measured - regression) ---
        residuals_plot = coeffVal - np.array(regression_at_points)

        #  --- Generate smooth AoA range for continuous curve ---
        aoa_smooth = np.linspace(min(aoa), max(aoa), 200)
        regression_smooth = [self.regressionPredict(alpha, coeff) for alpha in aoa_smooth]
        corrected_smooth = [
            self.regressionPredict(alpha, coeff) + self.errorcorrect(alpha, coeff)
            for alpha in aoa_smooth
        ]

        #  --- Plot setup ---
        plt.figure(figsize=(8, 5))

        # Regression and corrected curves
        plt.plot(aoa_smooth, regression_smooth, '--', label='Regression (Uncorrected)')
        plt.plot(aoa_smooth, corrected_smooth, '-', color='orange',
                linewidth=2, label='Hybrid (Corrected)')

        # Measured data points
        plt.scatter(aoa, coeffVal, color='red', zorder=5, label='Measured Data')

        # Residual bars showing correction magnitudes
        plt.errorbar(
            aoa,
            regression_at_points,
            yerr=np.abs(residuals_plot),
            fmt='none',
            ecolor='purple',
            elinewidth=1.5,
            capsize=4,
            label='Residual Correction'
        )

        plt.xlabel("Angle of Attack (°)")
        plt.ylabel(f"{coeff.upper()} Coefficient")
        plt.title("Hybrid Regression–Interpolation Model with Residual Corrections")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()

  

    

    


    

    








