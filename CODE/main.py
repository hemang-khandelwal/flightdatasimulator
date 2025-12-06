from Database.AeroModel import AeroModel
from Mechanics.forces import Mechanics

plane = AeroModel(1,1,20)
aoa = 12 
lift_val = plane.aeroval(aoa,"cl")

print("Lift Coeff", lift_val)

forces = Mechanics(plane,122,123)

l,d,m = forces.aeroForces(12,12,aoa)
print("Lift Force", l)
lhoriz = forces.resolveForce(aoa,l,"h")
print("Lift Horizontal Component", lhoriz)

plane.plotHybridFit("cl") 


# Currently it prints out the Coeff value for a specific aoa and then it spits out the actual force value 
# Afterwards it resolve the force in the correct direction 