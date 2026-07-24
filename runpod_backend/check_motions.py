import os
import glob
print("Directory /workspace/AnimatedDrawings/examples/config/motion:")
for p in glob.glob("/workspace/AnimatedDrawings/examples/config/motion/*.yaml"):
    print(p)
print("----------------")
print("Does examples/config/motion/jump.yaml exist?")
print(os.path.exists("/workspace/AnimatedDrawings/examples/config/motion/jump.yaml"))
