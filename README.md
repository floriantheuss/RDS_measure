# RDS_measure

A laboratory automation and data analysis package for **Resonant Drumhead Spectroscopy (RDS)** — a technique for characterizing mechanical resonances of membrane samples as a function of temperature and other experimental parameters.

The package provides a PyQt5-based GUI that orchestrates multiple laboratory instruments, automates data acquisition, performs signal processing, and fits Lorentzian resonance models to extract physical quantities such as resonance frequency (f₀), damping (γ), and mechanical quality factor (Q = f₀/γ).

---

## Overview

A typical RDS measurement proceeds as follows:

1. **Connect instruments** via the Device Manager (VNA, temperature controller, stages, camera, lock-in amplifier)
2. **Acquire frequency sweeps** using the Spectrum Recorder, which drives the VNA and records the complex transmission as a function of frequency, along with metadata (temperature, laser currents, VNA settings)
3. **Process and fit** the data in the Resonance Detector, which applies band-pass filtering and fits complex Lorentzian resonance peaks
4. **Track resonances** automatically: the Sweeper can adjust the VNA frequency window based on the last fitted resonance position
5. **Maintain alignment** using the camera-based auto-alignment system to keep the laser spot on the sample
6. **Monitor** temperature, lock-in output, and resistivity in parallel panels
7. **Export** fitted resonance parameters and metadata to `.dat` files for further analysis

---

## Modules

### `resonating_membranes_master.py`
Main application entry point. Launches the PyQt5 window and starts the Twisted async reactor. Manages all sub-windows and the shared `deviceDict` used to pass instrument handles between modules.

### `device_manager/`
Hardware abstraction layer. Supports:
- **Keysight/Agilent E5063A** — Vector Network Analyzer (VNA)
- **Lakeshore Model 331** — Cryogenic temperature controller
- **Keithley 2000** — Digital multimeter
- **Thorlabs KST201** — X/Y motorized translation stages
- **Thorlabs TDC001** — Z-axis translation stage
- **Signal Recovery 7265 DSP** — Lock-in amplifier
- **uEye UC480** — USB camera

### `spectrum_recorder/`
Controls the VNA to record frequency sweeps. Collects metadata (temperature, laser currents, VNA settings) and saves each sweep as a `.npz` file. Supports periodic acquisition and single-scan mode with optional auto-tracking and auto-alignment.

### `resonance_detector/`
Loads `.npz` or `.dat` sweep files, applies a configurable band-pass filter (Butterworth), and fits complex Lorentzian peaks using `lmfit`. Supports single-resonance manual fits and automated batch fitting across all sweep files in a directory. Results are saved as `.dat` files with full metadata.

**Resonance model:**

```
L(f) = A·exp(iφ) / (γ/2 − (f − f₀)·i)  +  c₀ + c₁·i  +  (m₀ + m₁·i)·f
```

where f₀ is the resonance frequency, γ the linewidth (damping), A the amplitude, φ the phase, and the remaining terms model a linear background.

### `camera_control/`
Live camera feed from a uEye UC480 camera with manual and automated sample alignment. Automated alignment registers the current image against a reference image using affine transforms (OpenCV) and iteratively drives the Thorlabs X/Y stages to minimize the offset.

### `resistivity_sweeper/`
Lock-in amplifier based AC resistance/impedance measurements as a function of temperature. Plots X, Y, amplitude, and phase in real time.

---

## Installation

### Python version

Python 3.8 or later is recommended (the package has been tested on Windows and macOS).

### Required packages

Install the core dependencies with pip:

```bash
pip install PyQt5 pyqtgraph twisted pyvisa numpy scipy lmfit matplotlib opencv-python imutils
```

| Package | Purpose |
|---|---|
| `PyQt5` | GUI framework (widgets, signals, `.ui` file loading) |
| `pyqtgraph` | Fast scientific plotting inside the GUI |
| `twisted` | Asynchronous I/O and reactor for non-blocking instrument communication |
| `pyvisa` | GPIB/USB/TCPIP instrument communication (IEEE 488.2) |
| `numpy` | Array operations, polynomial fitting, `.npz` file I/O |
| `scipy` | Butterworth filters, cubic spline interpolation |
| `lmfit` | Constrained least-squares Lorentzian fitting |
| `matplotlib` | Supplementary plotting (camera module) |
| `opencv-python` | Image registration and affine transforms for auto-alignment |
| `imutils` | Image utility helpers used in alignment routines |

### Instrument-specific drivers

Some instruments require additional drivers or packages that are not on PyPI:

| Instrument | Package / Driver |
|---|---|
| Thorlabs TDC001 Z-stage | `thorlabs_apt_device` — `pip install thorlabs-apt-device` |
| uEye UC480 camera | `instrumental` — `pip install instrumental-lib`; also requires the IDS uEye SDK from the IDS website |
| Thorlabs KST201 X/Y stages | Requires the Thorlabs Kinesis software and the `thorlabs_apt` or `thorlabs_apt_device` Python wrapper |

Additionally, a VISA backend must be installed for PyVISA to communicate with GPIB/USB instruments:

```bash
# Open-source option:
pip install pyvisa-py
# Or install National Instruments NI-VISA from ni.com
```

### Shared instrument libraries

The package imports custom instrument driver wrappers from a `shared.instrument_libraries` namespace (e.g., `keysight_e5063a`, `lakeshore_model331`, `keithley_2000multimeter`, `signal_recovery_7265_DSP`, `thorlabs_kst201`). Ensure the parent `measurement_control` directory containing the `shared/` package is on the Python path.

---

## Configuration

All configuration is managed through the GUIs and saved automatically — no manual file editing is needed. Instrument addresses entered in the Device Manager are saved when the window is closed. Filter and fit parameters set in the Resonance Detector are saved when applied. Camera control settings (stage calibration, laser spot position) are saved on close and whenever a reference image is captured.

The configuration is stored in JSON files inside each module's directory:
- `device_manager/config_devManager.json` — instrument VISA addresses and serial numbers
- `resonance_detector/config_plotter.json` — band-pass filter cutoffs and automated fit bounds
- `camera_control/config_cameraControl.json` — stage calibration, backlash, and laser spot position

---

## Running the application

```bash
python resonating_membranes_master.py
```

This opens the master window. From there, use the sub-panel buttons to open the Device Manager (connect instruments first), then the Spectrum Recorder or Resonance Detector as needed.

---

## Data format

Sweep files saved by the Spectrum Recorder are NumPy `.npz` archives with the following keys:

| Key | Description |
|---|---|
| `freq (Hz)` | Frequency array |
| `Real part (V)` | Real (X) component of complex transmission |
| `Imaginary part (V)` | Imaginary (Y) component |
| `temperature (K)` | Sample temperature at time of acquisition |
| `drive laser current (mA)` | Drive laser current |
| `probe laser current (mA)` | Probe laser current |
| `probe laser signal (mV)` | Multimeter reading of probe laser power |
| `VNA IF bandwidth (Hz)` | VNA intermediate frequency bandwidth |
| `VNA power (dBm)` | VNA output power |
| `VNA averaging` | Averaging on/off flag |
| `VNA averaging factor` | Number of averages |

Fitted resonance parameters are exported as tab-delimited `.dat` files.
