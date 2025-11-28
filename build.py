import subprocess
import glob
import os

# Build wheel with Hatch
subprocess.run("pip uninstall auto_cythonizer -y", shell=True, check=True)
subprocess.run("hatch build", shell=True, check=True)

# Auto-detect latest wheel
wheels = glob.glob(os.path.join("dist", "*.whl"))
if not wheels:
    raise RuntimeError("No wheel found in dist folder!")

latest_wheel = max(wheels, key=os.path.getmtime)
subprocess.run(f"pip install --upgrade {latest_wheel}", shell=True, check=True)
print(f"✅ Installed {latest_wheel}")

# Test the library
subprocess.run("auto-cythonizer -h", shell=True, check=True)
