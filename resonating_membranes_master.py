from PyQt5.QtWidgets import (QApplication,
                             QMainWindow,
                             QPushButton,
                             QHBoxLayout,
                             QVBoxLayout,
                             QWidget,
                             QFileDialog,
                             QTableWidget,
                             QTableWidgetItem,
                             QDockWidget)
from PyQt5.QtCore import QTimer
from PyQt5 import uic, QtCore
from PyQt5.QtGui import QIcon
from pathlib import Path
import ctypes
import pyvisa
from copy import deepcopy
import platform
from Resonating_Membranes.resonance_detector.resonance_detector import ResonanceDetector
from Resonating_Membranes.device_manager.device_manager import DeviceManager
from Resonating_Membranes.spectrum_recorder.sweeper import Sweeper
from Resonating_Membranes.camera_control.camera_control import Camera
from shared.vna_control.vna_control import VNAControl
from shared.temperature_control.temperature_control import TempControl
from shared.lockin_control.lockin_control import LockInControl
from Resonating_Membranes.resistivity_sweeper.data_view import DataViewer
from Resonating_Membranes.resistivity_sweeper.resistivity_sweeper import RhoSweeper



class ResonatingMembranesMaster (QMainWindow):
    def __init__(self, reactor):
        super(ResonatingMembranesMaster, self).__init__()

        self.reactor = reactor

        self.operating_system = platform.system()
        if self.operating_system in ['windows', 'Windows']:
            self.separator = '\\'
        elif self.operating_system in ['mac', 'Mac', 'Darwin', 'darwin']:
            self.separator = '/'
        else:
            print('operating system not any of the possible options')
            print('current operating system is: ', self.operating_system)


        # import ui file
        path     = str( Path(__file__).absolute() )
        temp     = path.split(self.separator)
        temp[-1] = 'resonating_membranes_master.ui'
        temp_ui     = self.separator.join(temp)
        uic.loadUi(temp_ui, self)

        # load window icon (only works on windows though ...)
        if self.operating_system in ['windows', 'Windows']:
            myappid = u'ResMem.Master'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            temp[-1] = 'resonating_membranes_logo.png'
            logo_path = self.separator.join(temp)
            icon = QIcon(logo_path)
            self.setWindowIcon(icon)        

        # initialize Resource Manager
        self.rm = pyvisa.ResourceManager()

        # initialize device manager
        self.deviceDict = {'temperature': None,
                            'aux': None,
                            'vna': None,
                            'multimeter': None,
                            'xstage': None,
                            'ystage': None,
                            'zstage': None,
                            'camera': None,
                            'lockin': None}
        self.IPaddressesDict = deepcopy(self.deviceDict)
        self.auxCommandDict = {'aux':None}
        self.deviceManagerWindow = DeviceManager(reactor=self.reactor, parent=self, operating_system=self.operating_system)
        self.DeviceManagerButton.clicked.connect(self.open_device_manager)

        # initialize resonance detector
        # I am initializing all these classes here (could have just done it once the button is clicked)
        # because this way, if the specific window is closed, the class still exists
        self.resonanceDetectorWindow = ResonanceDetector(operating_system=self.operating_system)
        self.ResonanceDetectorButton.clicked.connect(self.open_resonance_detector)

        # windows
        self.SweeperWindow = Sweeper(reactor=self.reactor, parent=self, operating_system=self.operating_system)
        self.SweeperButton.clicked.connect(self.open_sweeper)

        self.vnaMonitorWindow = VNAControl(reactor=self.reactor, parent=self, operating_system=self.operating_system)
        self.vnaMonitorButton.clicked.connect(self.open_vna_monitor)

        self.tempControlWindow = TempControl(reactor=self.reactor, parent=self, operating_system=self.operating_system)
        self.tempControlButton.clicked.connect(self.open_temp_control)

        self.cameraWindow = Camera(reactor=self.reactor, parent=self, operating_system=self.operating_system)
        self.cameraButton.clicked.connect(self.open_camera_window)

        self.lockinWindow = LockInControl(reactor=self.reactor, parent=self, operating_system=self.operating_system)
        self.lockinButton.clicked.connect(self.open_lockin_window)

        self.resistivityWindow = RhoSweeper(reactor=self.reactor, parent=self, operating_system=self.operating_system)
        self.resistivityButton.clicked.connect(self.open_resistivity_window)    

        # list of all windows so we can close them all when closing this window
        self.windows = [self.tempControlWindow, self.vnaMonitorWindow, self.resonanceDetectorWindow,
                        self.deviceManagerWindow, self.SweeperWindow,
                        self.cameraWindow, self.lockinWindow, self.resistivityWindow]

        # Connect the close event to the custom function
        self.closeEvent = self.on_close_event

    def update_all_device_dicts (self):
        self.tempControlWindow.update_device_dict()
        self.vnaMonitorWindow.update_device_dict()
        self.SweeperWindow.update_device_dict()
        self.cameraWindow.update_device_dict()
        self.lockinWindow.update_device_dict()
        self.resistivityWindow.update_device_dict()

    def open_resonance_detector(self):
        if self.resonanceDetectorWindow is None:
            self.resonanceDetectorWindow = ResonanceDetector(operating_system=self.operating_system)
        self.resonanceDetectorWindow.show()

    def open_device_manager(self):
        if self.deviceManagerWindow is None:
            self.deviceManagerWindow = DeviceManager(reactor=self.reactor, parent=self, operating_system=self.operating_system)
        self.deviceManagerWindow.show()

    def open_sweeper (self):
        if self.SweeperWindow is None:
            self.SweeperWindow = Sweeper(reactor=self.reactor, parent=self, operating_system=self.operating_system)
        self.SweeperWindow.show()
    
    def open_vna_monitor (self):
        if self.vnaMonitorWindow is None:
            self.vnaMonitorWindow = VNAControl(reactor=self.reactor, parent=self, operating_system=self.operating_system)
        self.vnaMonitorWindow.show()

    def open_temp_control (self):
        if self.tempControlWindow is None:
            self.tempControlWindow = TempControl(reactor=self.reactor, parent=self, operating_system=self.operating_system)
        self.tempControlWindow.show()

    def open_camera_window (self):
        if self.cameraWindow is None:
            self.cameraWindow = Camera(reactor=self.reactor, parent=self, operating_system=self.operating_system)
        self.cameraWindow.show()

    def open_lockin_window (self):
        if self.lockinWindow is None:
            self.lockinWindow = LockInControl(reactor=self.reactor, parent=self, operating_system=self.operating_system)
        self.lockinWindow.show()

    def open_resistivity_window (self):
        if self.resistivityWindow is None:
            self.resistivityWindow = RhoSweeper(reactor=self.reactor, parent=self, operating_system=self.operating_system)
        self.resistivityWindow.show()


    def on_close_event(self, event):
        # Run your function when the window is closed
        self.deviceManagerWindow.disconnect_all() #disconnect all devices

        try:
            self.rm.close()
            print('Success closing resource manager')
        except:
            print('Error closing resource manager')

        for window in self.windows:
            if not window is None:
                window.close()

        # Call the default closeEvent to close the window
        super().closeEvent(event)


if __name__ == '__main__':
    QApplication.setStyle('Fusion')
    app = QApplication([])
    app.setStyle('Windows')
    import qt5reactor
    qt5reactor.install()
    from twisted.internet import reactor
    win = ResonatingMembranesMaster(reactor)
    win.show()
    app.exec()