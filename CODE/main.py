from Database.AeroModel import AeroModel
from Mechanics.Forces import Forces
from Database.Environment import ISA

isa = ISA(1)
plane = AeroModel(1,1,20)
aoa = 12 
lift_val = plane.aeroval(aoa,"cl")

print("Lift Coeff", lift_val)

forces = Forces(plane,122,123)

l,d,m = forces.aeroForces(12,isa.density(28056),aoa)
print("Lift Force", l)
lhoriz = forces.resolveForce(aoa,l,"cos")
print("Lift Horizontal Component", lhoriz)

plane.plotHybridFit("cm") 

a = plane.maxValue("cm")

print(a)

# Currently it prints out the Coeff value for a specific aoa and then it spits out the actual force value 
# Afterwards it resolve the force in the correct direction 