from Database.AeroModel import AeroModel
from Mechanics.forces import Mechanics

plane = AeroModel(1,1,3)

lift_val = plane.aeroval(12,"cl")

print("Lift Val", lift_val)

plane.plotHybridFit("cl") 


