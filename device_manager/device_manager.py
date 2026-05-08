import pyvisa
import numpy as np
import sys
from pathlib import Path
import json
from copy import deepcopy
import ctypes
import twisted
from twisted.internet.defer import inlineCallbacks, Deferred
from instrument_libraries_and_control.instrument_libraries.keysight_e5063a import E5063A
from instrument_libraries_and_control.instrument_libraries.lakeshore_model331 import Model331
from instrument_libraries_and_control.instrument_libraries.keithley_2000multimeter import Multimeter2000
from instrument_libraries_and_control.instrument_libraries.signal_recovery_7265_DSP import SignalRecovery7265
from instrument_libraries_and_control.instrument_libraries.thorlabs_kst201_stepper_motor import ThorlabsKST201
from instrument_libraries_and_control.instrument_libraries.thorlabs_kiralux_camera import ThorlabsKiralux
from thorlabs_apt_device import TDC001

from PyQt5.QtWidgets import (QApplication,
                             QMainWindow,
                             QPushButton,
                             QHBoxLayout,
                             QVBoxLayout,
                             QWidget,
                             QFileDialog,
                             QTableWidget,
                             QTableWidgetItem)
from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5 import uic, QtCore
from PyQt5.QtGui import QIcon, QColor
import platform


class DeviceManager(QMainWindow):
    def __init__(self, reactor, parent=None, operating_system=None):
        super(DeviceManager, self).__init__()

        self.operating_system = operating_system
        if self.operating_system is None:
            self.operating_system = platform.system()
        if self.operating_system in ['windows', 'Windows']:
            self.separator = '\\'
        elif self.operating_system in ['mac', 'Mac', 'Darwin', 'darwin']:
            self.separator = '/'
        else:
            print('operating system not any of the possible options')
            print('current operating system is: ', operating_system)

        # import ui file
        path     = str( Path(__file__).absolute() )
        temp     = path.split(self.separator)
        temp[-1] = 'device_manager.ui'
        temp_ui     = self.separator.join(temp)
        uic.loadUi(temp_ui, self)

        # load window icon (only works on windows though ...)
        if self.operating_system in ['windows', 'Windows']:
            myappid = u'ResMem.DeviceManager'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            temp[-1] = 'device_manager_logo.png'
            logo_path = self.separator.join(temp)
            icon = QIcon(logo_path)
            self.setWindowIcon(icon)  

        self.reactor = reactor
        self.parent = parent
        self.init_config()
        # initialize devices
        if not self.parent is None:
            self.deviceDict = self.parent.deviceDict
            self.IPaddressesDict = self.parent.IPaddressesDict
            self.rm = self.parent.rm
            self.auxCommandDict = self.parent.auxCommandDict
        else:
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
            # start resource manager
            self.rm = pyvisa.ResourceManager()


        self.devIdentification = {
                'Cryo-con,22C,206008,3.19E': 'temperature',
                'Agilent Technologies,E5063A,MY54100795,A.02.09': 'vna',
                'KEITHLEY INSTRUMENTS INC.,MODEL 2000,0811270,A13  /A02': 'multimeter',
                'Thorlabs,APT DC Servo Controller,1000,1.1.0': 'zstage',
                'LSCI,MODEL331S,336079,120407': 'temperature',
                '7265': 'lockin'
                }

        # self.identify_resources()
        # self.TestIDNBtn.clicked.connect(self.testIDN)

        self.connectTempBtn.clicked.connect(lambda b, dev= "temperature" : self.connectDevice(b, dev))
        self.connectVNABtn.clicked.connect(lambda b, dev= "vna" : self.connectDevice(b, dev))
        self.connectMultimeterBtn.clicked.connect(lambda b, dev= "multimeter" : self.connectDevice(b, dev))
        self.connectAuxBtn.clicked.connect(lambda b, dev= "aux" : self.connectDevice(b, dev))
        self.connectLockInBtn.clicked.connect(lambda b, dev= "lockin" : self.connectDevice(b, dev))
        self.connectCameraBtn.clicked.connect(lambda b, dev= "camera" : self.connectDevice(b, dev))
        self.connectXStageBtn.clicked.connect(lambda b, dev= "xstage" : self.connectDevice(b, dev))
        self.connectYStageBtn.clicked.connect(lambda b, dev= "ystage" : self.connectDevice(b, dev))
        self.connectZStageBtn.clicked.connect(lambda b, dev= "zstage" : self.connectDevice(b, dev))

        self.reconnectAllBtn.clicked.connect(self.reconnect_all)
        
        # additional buttons and variables for the aux instrument
        self.auxTestBtn.clicked.connect(self.test_aux_cmd)
        self.auxCommandDict['aux'] = self.auxCommandLine.text()

        # Connect the close event to the custom function
        self.closeEvent = self.on_close_event


    
    def init_config (self):
        # import ui file
        path     = str( Path(__file__).absolute() )
        temp     = path.split(self.separator)
        temp[-1]         = 'config_devManager.json'
        self.config_path = self.separator.join(temp)
        with open(self.config_path, 'r') as openfile:
            self.config = json.load(openfile)
        
        self.tempIPAddressBox.setCurrentText(self.config['IP Addresses']['temperature'])
        self.vnaIPAddressBox.setCurrentText(self.config['IP Addresses']['vna'])
        self.multimeterIPAddressBox.setCurrentText(self.config['IP Addresses']['multimeter'])
        self.xstageIPAddressBox.setCurrentText(self.config['IP Addresses']['xstage'])
        self.ystageIPAddressBox.setCurrentText(self.config['IP Addresses']['ystage'])
        self.zstageIPAddressBox.setCurrentText(self.config['IP Addresses']['zstage'])
        self.cameraIPAddressBox.setCurrentText(self.config['IP Addresses']['camera'])
        self.lockinIPAddressBox.setCurrentText(self.config['IP Addresses']['lockin'])
        self.auxIPAddressBox.setCurrentText(self.config['IP Addresses']['aux'])
        self.auxCommandLine.setText(self.config['Aux Command'])
        
           
    @inlineCallbacks
    def identify_resources (self):
        """
        read *IDN? of all local resources in 'list_resources';
        check idn against known idn's to identify the type of resource;
        i.e. is it a temperature control, of a magnet control, or a scope, ...
        """
        print(self.rm.list_resources())
        for resource in self.rm.list_resources():
            if self.operating_system in ['windows', 'Windows']:
                boolean = (resource.find('TCPIP') < 0) and (resource.find('ASRL1::INSTR')<0)            
            elif self.operating_system in ['mac', 'Mac', 'Darwin', 'darwin']:
                boolean = (resource.find('TCPIP') < 0) and (resource.find('ASRL1::INSTR')<0) and (resource.find('ASRL2::INSTR')<0) and (resource.find('ASRL3::INSTR')<0) and (resource.find('ASRL4::INSTR')<0)
            if boolean: # make sure to only check local instruments; ignore instrument connected via ethernet (could lead to communication problems if someone else is using it currently)
                try:
                    adapter = self.rm.open_resource(resource)
                    idn = yield adapter.query('*IDN?').strip()
                    classification = self.devIdentification[idn]
                    adapter.close()
                    if classification == 'temperature':
                        self.tempIPAddressBox.addItem(resource)
                        self.auxIPAddressBox.addItem(resource) #always also add to aux - aux could be a second temperature ...
                    if classification == 'vna':
                        self.vnaIPAddressBox.addItem(resource)
                        self.auxIPAddressBox.addItem(resource) #always also add to aux - aux could be a second temperature for example ...
                    if classification == 'multimeter':
                        self.multimeterIPAddressBox.addItem(resource)
                        self.auxIPAddressBox.addItem(resource) #always also add to aux - aux could be a second temperature for example ...
                    if classification == 'xstage':
                        self.zstageIPAddressBox.addItem(resource)
                        self.auxIPAddressBox.addItem(resource) #always also add to aux - aux could be a second temperature for example ...
                    if classification == 'ystage':
                        self.zstageIPAddressBox.addItem(resource)
                        self.auxIPAddressBox.addItem(resource) #always also add to aux - aux could be a second temperature for example ...
                    if classification == 'zstage':
                        self.zstageIPAddressBox.addItem(resource)
                        self.auxIPAddressBox.addItem(resource) #always also add to aux - aux could be a second temperature for example ...
                    if classification == 'camera':
                        self.cameraIPAddressBox.addItem(resource)
                        self.auxIPAddressBox.addItem(resource) #always also add to aux - aux could be a second temperature for example ...
                    if classification == 'lockin':
                        self.lockinIPAddressBox.addItem(resource)
                        self.auxIPAddressBox.addItem(resource) #always also add to aux - aux could be a second temperature for example ...
                    else:
                        self.auxIPAddressBox.addItem(resource)
                        
                except Exception as e:
                    print(e)
                    adapter.close()

    
    def connectDevice(self, c, device):
        if self.deviceDict[device] is None:
            if device == 'temperature':
                try:
                    IPaddress = self.tempIPAddressBox.currentText()
                    temp_inst = self.rm.open_resource(IPaddress)
                    temp_device = Model331(temp_inst)
                    self.deviceDict[device] = temp_device
                    self.IPaddressesDict[device] = IPaddress
                    self.connectTempBtn.setText("Disconnect")
                    self.connectTempBtn.setStyleSheet("QPushButton#connectTempBtn {color: rgb(255, 0, 0);background-color:rgb(0,0,0);border: 2px solid rgb(255, 0, 0);border-radius: 5px}")
                except Exception as e:
                    print('Could not connect to temperature device ...')
                    print(e)
            if device == 'vna':
                try:
                    IPaddress  = self.vnaIPAddressBox.currentText()
                    vna_inst   = self.rm.open_resource(IPaddress)
                    vna_device = E5063A(vna_inst)
                    self.deviceDict[device] = vna_device
                    self.IPaddressesDict[device] = IPaddress
                    self.connectVNABtn.setText("Disconnect")
                    self.connectVNABtn.setStyleSheet("QPushButton#connectVNABtn {color: rgb(255, 0, 0);background-color:rgb(0,0,0);border: 2px solid rgb(255, 0, 0);border-radius: 5px}")
                except Exception as e:
                    print('Could not connect to vna device ...')
                    print(e)
            if device == 'multimeter':
                try:
                    IPaddress  = self.multimeterIPAddressBox.currentText()
                    multimeter_inst   = self.rm.open_resource(IPaddress)
                    multimeter_device = Multimeter2000(multimeter_inst)
                    self.deviceDict[device] = multimeter_device
                    self.IPaddressesDict[device] = IPaddress
                    self.connectMultimeterBtn.setText("Disconnect")
                    self.connectMultimeterBtn.setStyleSheet("QPushButton#connectMultimeterBtn {color: rgb(255, 0, 0);background-color:rgb(0,0,0);border: 2px solid rgb(255, 0, 0);border-radius: 5px}")
                except Exception as e:
                    print('Could not connect to multimeter device ...')
                    print(e)
            if device == 'xstage':
                try:
                    IPaddress  = self.xstageIPAddressBox.currentText()
                    xstage_device = ThorlabsKST201(IPaddress, polling_interval=700)    
                    xstage_device.connect()
                    self.deviceDict[device] = xstage_device
                    self.IPaddressesDict[device] = IPaddress
                    self.connectXStageBtn.setText("Disconnect")
                    self.connectXStageBtn.setStyleSheet("QPushButton#connectXStageBtn {color: rgb(255, 0, 0);background-color:rgb(0,0,0);border: 2px solid rgb(255, 0, 0);border-radius: 5px}")
                except Exception as e:
                    print('Could not connect to x stage device ...')
                    print(e)
            if device == 'ystage':
                try:
                    IPaddress  = self.ystageIPAddressBox.currentText()
                    ystage_device = ThorlabsKST201(IPaddress, polling_interval=700)    
                    ystage_device.connect()
                    self.deviceDict[device] = ystage_device
                    self.IPaddressesDict[device] = IPaddress
                    self.connectYStageBtn.setText("Disconnect")
                    self.connectYStageBtn.setStyleSheet("QPushButton#connectYStageBtn {color: rgb(255, 0, 0);background-color:rgb(0,0,0);border: 2px solid rgb(255, 0, 0);border-radius: 5px}")
                except Exception as e:
                    print('Could not connect to y stage device ...')
                    print(e)
            if device == 'zstage':
                try:
                    IPaddress  = self.zstageIPAddressBox.currentText()
                    # zstage_inst   = self.rm.open_resource(IPaddress)
                    # zstage_device = TDC001(zstage_inst)
                    if IPaddress.find('COM') >= 0:
                        zstage_device = TDC001(serial_port=IPaddress, home=False)
                    elif len(IPaddress.strip()) == 0:
                        zstage_device = TDC001(home=False)
                    else:
                        raise Exception('zstage device not connected yet; IP address must be COM port or empty ...')
                    self.deviceDict[device] = zstage_device
                    self.IPaddressesDict[device] = IPaddress
                    self.connectZStageBtn.setText("Disconnect")
                    self.connectZStageBtn.setStyleSheet("QPushButton#connectZStageBtn {color: rgb(255, 0, 0);background-color:rgb(0,0,0);border: 2px solid rgb(255, 0, 0);border-radius: 5px}")
                except Exception as e:
                    print('Could not connect to z stage device ...')
                    print(e)
            if device == 'camera':
                try:
                    IPaddress  = self.cameraIPAddressBox.currentText()
                    if IPaddress == '':
                        IPaddress = None
                    # IPaddress  = int(IPaddress)
                    # camera_inst   = self.rm.open_resource(IPaddress)
                    # camera_device = uc480.UC480_Camera(id=IPaddress, reopen_policy='new')
                    # camera_device = uc480.UC480_Camera(id=1, reopen_policy='new')
                    camera_device = ThorlabsKiralux(IPaddress)
                    camera_device.connect()
                    self.deviceDict[device] = camera_device
                    self.IPaddressesDict[device] = IPaddress
                    self.connectCameraBtn.setText("Disconnect")
                    self.connectCameraBtn.setStyleSheet("QPushButton#connectCameraBtn {color: rgb(255, 0, 0);background-color:rgb(0,0,0);border: 2px solid rgb(255, 0, 0);border-radius: 5px}")
                except Exception as e:
                    print('Could not connect to camera device ...')
                    print(e)
            if device == 'lockin':
                try:
                    IPaddress = self.lockinIPAddressBox.currentText()
                    lockin_inst = self.rm.open_resource(IPaddress)
                    lockin_device = SignalRecovery7265(lockin_inst)
                    self.deviceDict[device] = lockin_device
                    self.IPaddressesDict[device] = IPaddress
                    self.connectLockInBtn.setText("Disconnect")
                    self.connectLockInBtn.setStyleSheet("QPushButton#connectLockInBtn {color: rgb(255, 0, 0);background-color:rgb(0,0,0);border: 2px solid rgb(255, 0, 0);border-radius: 5px}")
                except Exception as e:
                    print('Could not connect to lockin device ...')
                    print(e)
            if device == 'aux':
                try:
                    IPaddress = self.auxIPAddressBox.currentText()
                    aux_device = self.rm.open_resource(IPaddress)
                    self.deviceDict[device] = aux_device
                    self.IPaddressesDict[device] = IPaddress
                    self.connectAuxBtn.setText("Disconnect")
                    self.connectAuxBtn.setStyleSheet("QPushButton#connectAuxBtn {color: rgb(255, 0, 0);background-color:rgb(0,0,0);border: 2px solid rgb(255, 0, 0);border-radius: 5px}")
                except Exception as e:
                    print('Could not connect to aux device ...')
                    print(e)
        
        else:
            if device == 'temperature':
                try:
                    self.deviceDict[device].close_dev()
                    self.deviceDict[device] = None
                    self.IPaddressesDict[device] = None
                    self.connectTempBtn.setText("Connect")
                    self.connectTempBtn.setStyleSheet("QPushButton#connectTempBtn {color: rgb(0, 255, 0);background-color:rgb(0,0,0);border: 2px solid rgb(0, 255, 0);border-radius: 5px}")
                except Exception as e:
                    print('Could not disconnect from temperature device ...')
                    print(e)
            if device == 'vna':
                try:
                    self.deviceDict[device].close_dev()
                    self.deviceDict[device] = None
                    self.IPaddressesDict[device] = None
                    self.connectVNABtn.setText("Connect")
                    self.connectVNABtn.setStyleSheet("QPushButton#connectVNABtn {color: rgb(0, 255, 0);background-color:rgb(0,0,0);border: 2px solid rgb(0, 255, 0);border-radius: 5px}")
                except Exception as e:
                    print('Could not disconnect from vna device ...')
                    print(e)
            if device == 'multimeter':
                try:
                    self.deviceDict[device].close_dev()
                    self.deviceDict[device] = None
                    self.IPaddressesDict[device] = None
                    self.connectMultimeterBtn.setText("Connect")
                    self.connectMultimeterBtn.setStyleSheet("QPushButton#connectMultimeterBtn {color: rgb(0, 255, 0);background-color:rgb(0,0,0);border: 2px solid rgb(0, 255, 0);border-radius: 5px}")
                except Exception as e:
                    print('Could not disconnect from multimeter device ...')
                    print(e)
            if device == 'xstage':
                try:
                    self.deviceDict[device].close_dev()
                    self.deviceDict[device] = None
                    self.IPaddressesDict[device] = None
                    self.connectXStageBtn.setText("Connect")
                    self.connectXStageBtn.setStyleSheet("QPushButton#connectXStageBtn {color: rgb(0, 255, 0);background-color:rgb(0,0,0);border: 2px solid rgb(0, 255, 0);border-radius: 5px}")
                except Exception as e:
                    print('Could not disconnect from x stage device ...')
                    print(e)
            if device == 'ystage':
                try:
                    self.deviceDict[device].close_dev()
                    self.deviceDict[device] = None
                    self.IPaddressesDict[device] = None
                    self.connectYStageBtn.setText("Connect")
                    self.connectYStageBtn.setStyleSheet("QPushButton#connectYStageBtn {color: rgb(0, 255, 0);background-color:rgb(0,0,0);border: 2px solid rgb(0, 255, 0);border-radius: 5px}")
                except Exception as e:
                    print('Could not disconnect from x stage device ...')
                    print(e)
            if device == 'zstage':
                try:
                    self.deviceDict[device].close()
                    self.deviceDict[device] = None
                    self.IPaddressesDict[device] = None
                    self.connectZStageBtn.setText("Connect")
                    self.connectZStageBtn.setStyleSheet("QPushButton#connectZStageBtn {color: rgb(0, 255, 0);background-color:rgb(0,0,0);border: 2px solid rgb(0, 255, 0);border-radius: 5px}")
                except Exception as e:
                    print('Could not disconnect from z stage device ...')
                    print(e)
            if device == 'camera':
                try:
                    self.deviceDict[device].close_dev()
                    self.deviceDict[device] = None
                    self.IPaddressesDict[device] = None
                    self.connectCameraBtn.setText("Connect")
                    self.connectCameraBtn.setStyleSheet("QPushButton#connectCameraBtn {color: rgb(0, 255, 0);background-color:rgb(0,0,0);border: 2px solid rgb(0, 255, 0);border-radius: 5px}")
                except Exception as e:
                    print('Could not disconnect from camera device ...')
                    print(e)
            if device == 'lockin':
                try:
                    self.deviceDict[device].close_dev()
                    self.deviceDict[device] = None
                    self.IPaddressesDict[device] = None
                    self.connectLockInBtn.setText("Connect")
                    self.connectLockInBtn.setStyleSheet("QPushButton#connectLockInBtn {color: rgb(0, 255, 0);background-color:rgb(0,0,0);border: 2px solid rgb(0, 255, 0);border-radius: 5px}")
                except Exception as e:
                    print('Could not disconnect from lockin device ...')
                    print(e)
            if device == 'aux':
                try:
                    self.deviceDict[device].close()
                    self.deviceDict[device] = None
                    self.IPaddressesDict[device] = None
                    self.connectAuxBtn.setText("Connect")
                    self.connectAuxBtn.setStyleSheet("QPushButton#connectAuxBtn {color: rgb(0, 255, 0);background-color:rgb(0,0,0);border: 2px solid rgb(0, 255, 0);border-radius: 5px}")
                except Exception as e:
                    print('Could not disconnect from aux device ...')
                    print(e)
        self.parent.deviceDict = self.deviceDict
        self.parent.update_all_device_dicts()

    
    # @inlineCallbacks
    # def testIDN (self, c=None):
    #     try:
    #         device = self.testIDNcomboBox.currentText()
    #         idn = yield self.deviceDict[device].query('*IDN?').strip()
    #         self.testIDNLine.setText(idn)
    #         return
    #     except Exception as e:
    #         self.testIDNLine.setText('nan')
    #         print('could not find IDN of device ...')
    #         print(e)


    @inlineCallbacks
    def test_aux_cmd (self, c=None):
        try:
            self.auxCommandDict['aux'] = self.auxCommandLine.text()
            output = yield self.deviceDict['aux'].query(self.auxCommandDict['aux']).strip()
            self.auxTestLine.setText(output)
        except Exception as e:
            self.auxTestLine.setText('nan')
            print('could not query cmd for aux device ...')
            print(e)

    
    def disconnect_all (self):
        for device in self.deviceDict:
            if not self.deviceDict[device] is None:
                try:
                    self.connectDevice(c=None, device=device)
                    print(f'disconnecting from {device} device successful')
                except Exception as e:
                    print(f'error disconnecting from {device} device')

    
    @inlineCallbacks
    def reconnect_all (self, c=None):
        ipaddresses = deepcopy(self.IPaddressesDict) # this is to remember which devices were connected
        # disconnect all existing connections
        self.disconnect_all()
        print('all devices closed ...')
        yield self.sleep(1)
        # make connections to all previously connected devices
        for device in ipaddresses:
            if not ipaddresses[device] is None:
                self.connectDevice(c=None, device=device)
        print('devices reconnected')


    def save_config (self):
        self.config['IP Addresses']['temperature'] = self.tempIPAddressBox.currentText()
        self.config['IP Addresses']['vna'] = self.vnaIPAddressBox.currentText()
        self.config['IP Addresses']['aux'] = self.auxIPAddressBox.currentText()
        self.config['IP Addresses']['multimeter'] = self.multimeterIPAddressBox.currentText()
        self.config['IP Addresses']['xstage'] = self.xstageIPAddressBox.currentText()
        self.config['IP Addresses']['ystage'] = self.ystageIPAddressBox.currentText()
        self.config['IP Addresses']['zstage'] = self.zstageIPAddressBox.currentText()
        self.config['IP Addresses']['camera'] = self.cameraIPAddressBox.currentText()
        self.config['IP Addresses']['lockin'] = self.lockinIPAddressBox.currentText()
        self.config['Aux Command']  = self.auxCommandLine.text()
        with open(self.config_path, "w") as outfile:
            json.dump(self.config, outfile, indent=4)


    def on_close_event(self, event):
        # Run your function when the window is closed
        self.save_config()

        # Call the default closeEvent to close the window
        super().closeEvent(event)  

    #async sleep function - GUI is operable while function sleeps
    def sleep(self, secs):
        d = Deferred()
        self.reactor.callLater(secs,d.callback,'Sleeping')
        return d
