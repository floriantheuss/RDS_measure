# For camera
## Installation
- Install ThorCam software from http://thorlabs.com/software-pages/ThorCam — this installs the USB camera drivers. Do **not** install ThorImageCAM instead; it does not install the drivers in the correct place. "Installing on local hard drive" is enough
    - during installation make sure to actually select the USB driver for installation. 
- From the same page, go to the "Programming Interfaces" tab and download "Windows SDK and Doc. for Scientific Cameras". This contains the native DLLs and Python source examples but you do not need to use the bundled DLLs directly (see below).

## Python setup

Install the Python SDK package into your environment using pip:
```
pip install thorlabs_tsi_camera_python_sdk_package.zip      # you may have to specify the full file path for the zip file
```
The zip is found in `Scientific Camera Interfaces\SDK\Python Toolkit\` inside the downloaded SDK folder. This installs the `thorlabs_tsi_sdk` package.

That should have created a `thorlabs_tsi_sdk` package folder in your `Lib/site-packages` folder in your python environment. Now, inside the downloaded SDK folder at `Scientific Camera Interfaces\SDK\Native Toolkit\dlls`, copy the `Native_64_lib` folder into that `thorlabs_tsi_sdk` package folder (copy the entire folder not just its contents).

- you can now delete the downloaded SDK folder if you want to

## Connecting to the camera in Python

Python 3.8+ on Windows changed how DLLs are loaded. Adding the DLL folder to `PATH` alone is not sufficient. You need two things before importing the SDK:

1. `os.add_dll_directory(dll_path)` — registers the folder with Python's DLL loader so ctypes can find `thorlabs_tsi_camera_sdk.dll` on import.
2. `os.environ['PATH'] = dll_path + os.pathsep + os.environ['PATH']` — needed so that once the main SDK DLL is running, its internal `LoadLibrary` calls (to load USB transport plugins like `thorlabs_ccd_tsi_usb.dll`) can also find their dependencies.

Both must point to the DLL folder bundled with the installed package. Resolve it dynamically so it works regardless of environment:

```python
import os
import thorlabs_tsi_sdk

_dll_path = os.path.join(os.path.dirname(thorlabs_tsi_sdk.__file__), 'Native_64_lib')
os.environ['PATH'] = _dll_path + os.pathsep + os.environ['PATH']
os.add_dll_directory(_dll_path)

from thorlabs_tsi_sdk.tl_camera import TLCameraSDK
```

`import thorlabs_tsi_sdk` at the top is safe — the package `__init__.py` does not load any DLLs, so the DLL path setup that follows it still runs before any native code is touched.


# For KST201 stepper motors

## Installation
Install Kinesis software from https://www.thorlabs.com/software-pages/motion_control;
this installs necessary drivers

## Python
- in the folder where the Kinesis software is installed (typically: `C:\\Program Files\\Thorlabs\\Kinesis\\`) you will find many dll files
- in the driver for the stepper motor, add the following dll's to your .NET library
### Add References to .NET libraries
    kinesis_dir = "C:\\Program Files\\Thorlabs\\Kinesis\\"
    clr.AddReference(f"{kinesis_dir}Thorlabs.MotionControl.DeviceManagerCLI.dll")
    clr.AddReference(f"{kinesis_dir}Thorlabs.MotionControl.GenericMotorCLI.dll")
    clr.AddReference(f"{kinesis_dir}ThorLabs.MotionControl.KCube.StepperMotorCLI.dll")
### Import relevant packages
    from Thorlabs.MotionControl.DeviceManagerCLI import *
    from Thorlabs.MotionControl.GenericMotorCLI import *
    from Thorlabs.MotionControl.KCube.StepperMotorCLI import *

### Tips
The Kinesis installation folder also includes a `Thorlabs.MotionControl.DotNet_API.chm` file. This is a compiled HTML file, includes some commands, etc. Could be helpful if you want to add to the stepper motor driver