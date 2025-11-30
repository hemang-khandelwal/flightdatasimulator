import numpy as np 
import matplotlib.pyplot as plt



#aoa = [-2, 0, 2, 4, 6, 8, 10]
#cl = [-0.2, 0.0, 0.2, 0.4, 0.7, 0.9, 1.0]
aoa = [0.01,0.02,0.03,0.04,0.05,0.06,0.07,0.08,0.09,0.1,0.11,0.12]
cl = [350,670,1100,1600,2000,2400,2900,3400,2900,4400,5000,5200]
#aoa = np.linspace(-10, 10, 12)  # evenly spaced angles
#cl = np.random.uniform(-1, 1, len(aoa))  


degree = 2
new = np.array([])

for i in range (0,len(aoa)):
    for b in range (0,degree):
        #print(aoa[i])
        number = aoa[i] ** b
        #print(number)
        new = np.append(new, number)

#new = new.reshape(len(aoa),degree)

rows = len(aoa)
cols = degree 

matrix = [] 

for c in range (rows):
    row = []
    for d in range(cols):
        index = c * cols + d 
        row.append(new[index])

    matrix.append(row)


matrix = [[float(value) for value in row] for row in matrix]
print(matrix)

yvals = []
for value in cl:
    yvals.append([value])


print(yvals)

result = []
def transpose(matrix):
    rows = len(matrix)
    cols = len(matrix[0])
    result = [[0 for _ in range(rows)] for _ in range(cols)]
    for i in range(rows):
        for j in range(cols):
            result[j][i] = matrix[i][j]

    return result

print("Transpose")
result = transpose(matrix)

print(result)

X = np.array(matrix)
Xt = np.array(result)
y = np.array(yvals)

XXt = Xt @ X


inv = np.linalg.inv(XXt)

xty = Xt @ y 

a = inv @ xty 

print(a)


def predict(x,a): 
    total = 0 
    for power, coeff in enumerate(a):
        total += coeff * (x**power)
    return total 



total = predict(2,a)

global residuals 
residuals = []

def residualcalc(num):
    residuals.clear()
    for ind,number in enumerate(aoa): 
        error = cl[ind] - predict(number,a)
        residuals.append(error)
    return residuals[aoa.index(num)]

print(residuals)
 
## IN THE DESIGN SECTION FOR THE CODE JUST SAY HOW I DID THE LINEAR INTERPOLATION AND MADE THE GRAIDENT THE FIRST AND THE LAST POINT IN THE 
# RESIDUAL ARRAY, BUT INSTEAD IM GOING TO FIND THE 2 CLOSEST POINTS AND USE THEM 

def errorcorrect(value, residuals): 
    for y in range(len(aoa)-1):
        a1,a2 = aoa[y], aoa[y+1]
        r1, r2 = residualcalc(a1), residualcalc(a2)

        if a1 <= value <= a2: 
            ans = r1 + ((r2 - r1) / (a2 - a1)) * (value - a1)
            return ans 
        
    if value < aoa[0]:
        return residuals[0]
    else:
        return residuals[-1]

t = 40
print(predict(t,a))
print(predict(t,a)+ errorcorrect(t,residuals))




####

#

##

# --- assume these are already defined ---
# aoa, cl, a, residuals, predict(), errorcorrect()

# Regression (uncorrected) and corrected values at measured points
regression_at_points = [predict(alpha, a) for alpha in aoa]
corrected_at_points = [predict(alpha, a) + errorcorrect(alpha, residuals) for alpha in aoa]

# Residuals = measured - regression (the vertical "correction")
residuals_plot = [cl[i] - regression_at_points[i] for i in range(len(aoa))]

# --- Create smooth curves for visual continuity ---
aoa_smooth = np.linspace(min(aoa), max(aoa), 200)
regression_smooth = [predict(alpha, a) for alpha in aoa_smooth]
corrected_smooth = [predict(alpha, a) + errorcorrect(alpha, residuals) for alpha in aoa_smooth]

# --- Plot everything ---
plt.figure(figsize=(8,5))
plt.plot(aoa_smooth, regression_smooth, '--', label='Regression (Uncorrected)')
plt.plot(aoa_smooth, corrected_smooth, '-', label='Hybrid (Corrected)', color='orange', linewidth=2)

# Plot measured data
plt.scatter(aoa, cl, color='red', zorder=5, label='Measured Data')

# --- Add residual corrections as error bars ---
plt.errorbar(
    np.ravel(aoa),                        # flatten x
    np.ravel(regression_at_points),       # flatten y
    yerr=np.abs(np.ravel(residuals_plot)),  # flatten error
    fmt='none',
    ecolor='purple',
    elinewidth=1.5,
    capsize=4,
    label='Residual Correction'
)

# --- Styling ---
plt.xlabel("Angle of Attack (°)")
plt.ylabel("Lift Coefficient CL")
plt.title("Hybrid Regression–Interpolation Model with Residual Corrections")
plt.legend()
plt.grid(True)
plt.show()
