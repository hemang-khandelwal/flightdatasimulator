from Database.AeroModel import AeroModel
from Mechanics.Forces import Forces
from Database.Environment import ISA
import numpy as np

isa = ISA(1)
plane = AeroModel(1,1,20)
aoa = np.deg2rad(12)  # working in radians internally
lift_val = plane.aeroval(aoa,"cl")

print("Lift Coeff", lift_val)

forces = Forces(plane,122,123)

l,d,m = forces.aeroForces(
    density=isa.density(28056),
    resulantV=12,
    aoa=aoa,
    limit_aoa=True
)
print("Lift Force", l)
lhoriz = forces.resolveForce(aoa,l,"cos")
print("Lift Horizontal Component", lhoriz)

plane.plotHybridFit("cl") 

a = plane.maxValue("cl")

print(a)

# Currently it prints out the Coeff value for a specific aoa and then it spits out the actual force value 
# Afterwards it resolve the force in the correct direction 

