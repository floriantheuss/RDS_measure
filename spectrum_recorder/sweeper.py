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
import pyqtgraph as pg
from pathlib import Path
import numpy as np
import threading
from time import time
import os
import sys
from copy import deepcopy
import ctypes
import json
from numpy.polynomial import polynomial
import platform
import twisted
from twisted.internet.defer import inlineCallbacks, Deferred
from datetime import datetime


class Sweeper (QMainWindow):
    def __init__(self, reactor, parent=None, operating_system=None):
        super(Sweeper, self).__init__()
        
        self.operating_system = operating_system
        if operating_system is None:
            self.operating_system = platform.system()
        if operating_system in ['windows', 'Windows']:
            self.separator = '\\'
        elif operating_system in ['mac', 'Mac', 'Darwin', 'darwin']:
            self.separator = '/'
        else:
            print('operating system not any of the possible options')
            print('current operating system is: ', operating_system)
        
        # import ui file
        path     = str( Path(__file__).absolute() )
        temp     = path.split(self.separator)
        temp[-1] = 'sweeper.ui'
        temp_ui     = self.separator.join(temp)
        uic.loadUi(temp_ui, self)

        # load window icon (only works on windows though ...)
        if self.operating_system in ['windows', 'Windows']:
            myappid = u'ResMem.Sweeper'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            temp[-1] = 'sweeper_logo.jpg'
            logo_path = self.separator.join(temp)
            icon = QIcon(logo_path)
            self.setWindowIcon(icon)  

        self.parent  = parent
        self.reactor = reactor
        self.vnaDevice = self.parent.deviceDict['vna']
        self.tempDevice = self.parent.deviceDict['temperature']
        self.multimeterDevice = self.parent.deviceDict['multimeter'] # changes here
        self.opticoolDevice = self.parent.deviceDict['opticool']
        self.f, self.X, self.Y = [], [], []
        self.temp = 0
        self.opticool_control_temp = 0
        self.opticool_aux_temp     = 0
        self.opticool_field        = 0
        self.ch = self.channelBox.currentText()
        
        self.initialize_directory_widgets()
        self.initialize_auto_save_widgets()

# changes here
    def update_device_dict (self):
        self.tempDevice = self.parent.deviceDict['temperature']
        self.vnaDevice = self.parent.deviceDict['vna']
        self.multimeterDevice = self.parent.deviceDict['multimeter']    # changes here
        self.opticoolDevice = self.parent.deviceDict['opticool']

    def initialize_directory_widgets (self):
        self.save_dir = None
        self.fileDialog = QFileDialog()
        self.browseButton.clicked.connect(self.browse_button_clicked)
        return 1
    
    def initialize_external_windows (self):
        self.vnaMonitorWindow = None
    
    def browse_button_clicked (self):
        try:
            if self.save_dir is not None:
                self.save_dir = self.fileDialog.getExistingDirectory(self, "Select Directory", self.save_dir)
            else:
                self.save_dir = self.fileDialog.getExistingDirectory(self, "Select Directory")
            self.directoryLine.setText(self.save_dir)
        except Exception as e:
            print("Error specifying save directory ...")
            print(e)
    
    # changes here
    def create_save_path (self):
        if self.save_dir is not None:
            path = self.save_dir + self.separator
        else:
            path = ''

        path = path + datetime.today().strftime('%Y-%m-%d_%H-%M-%S')
        if self.customCheck.isChecked():
            path = path + '_' + self.customNameLine.text()

        path = path + '.npz'
        return path
    
    # def on_close_event(self, event):
    #     if not self.vnaMonitorWindow is None:
    #         self.vnaMonitorWindow.close()

    #     # Call the default closeEvent to close the window
    #     super().closeEvent(event)

    def initialize_auto_save_widgets(self):
        self.autosaving = False
        self.autoSaveButton.setStyleSheet("QPushButton#autoSaveButton {color: rgb(0, 255, 0);background-color:rgb(0, 0, 0);border: 2px solid rgb(0, 255, 0);border-radius: 5px}")
        self.autoSaveButton.clicked.connect(self.auto_save_button_clicked)

# changes here
    @inlineCallbacks
    def auto_save_button_clicked (self, c=None):
        if self.autosaving:
            self.autosaving = False
            self.autoSaveButton.setStyleSheet("QPushButton#autoSaveButton {color: rgb(0, 255, 0);background-color:rgb(0, 0, 0);border: 2px solid rgb(0, 255, 0);border-radius: 5px}")
            self.autoSaveButton.setText('Start Auto Save')
            self.saveOptionBox.setEnabled(True)
            self.channelBox.setEnabled(True)
            self.tempCheck.setEnabled(True)
            self.customCheck.setEnabled(True)
            self.customNameLine.setEnabled(True)
            self.browseButton.setEnabled(True)
            self.directoryLine.setEnabled(True)
            self.dcSignalCheck.setEnabled(True)
            self.driveLaserCheck.setEnabled(True)
            self.probeLaserCheck.setEnabled(True)
            self.driveLaserCurrentLine.setEnabled(True)
            self.probeLaserCurrentLine.setEnabled(True)
            self.opticoolControlTempCheck.setEnabled(True)
            self.opticoolAuxTempCheck.setEnabled(True)
            self.opticoolMagnetCheck.setEnabled(True)
            yield self.vnaDevice.sweep_type('LIN')
            # self.vnaDevice.abort_sweeping()
        else:
            self.autosaving = True
            self.autoSaveButton.setStyleSheet("QPushButton#autoSaveButton {color: rgb(255, 0, 0);background-color:rgb(0, 0, 0);border: 2px solid rgb(255, 0, 0);border-radius: 5px}")
            self.autoSaveButton.setText('Stop Auto Save')
            self.saveOptionBox.setEnabled(False)
            self.tempCheck.setEnabled(False)
            self.channelBox.setEnabled(False)
            self.customCheck.setEnabled(False)
            self.customNameLine.setEnabled(False)
            self.browseButton.setEnabled(False)
            self.directoryLine.setEnabled(False)
            self.dcSignalCheck.setEnabled(False)
            self.driveLaserCheck.setEnabled(False)
            self.probeLaserCheck.setEnabled(False)
            self.driveLaserCurrentLine.setEnabled(True)
            self.probeLaserCurrentLine.setEnabled(True)
            self.opticoolControlTempCheck.setEnabled(False)
            self.opticoolAuxTempCheck.setEnabled(False)
            self.opticoolMagnetCheck.setEnabled(False)
            self.autosave()
        return 1
    
    # there are changes here
    # def save_trace (self, path, save_dict):
        # header = f'T={temp} K\nf (Hz), Real (V), Imaginary (V)'
        # data   = np.array([f, X, Y]).T
        # np.savez_compressed(path, **save_dict)


    # def save_trace (self, path, f, X, Y, temp):
    #     header = f'T={temp} K\nf (Hz), Real (V), Imaginary (V)'
    #     data   = np.array([f, X, Y]).T
    #     np.savetxt(path, data, header=header, delimiter=',')

    # this function has changes changes here
    @inlineCallbacks
    def collect_meta_data (self, c=None):
        drive_laser_current = 0
        probe_laser_current = 0
        custom_text         = 0
        dcSignal            = 0                   
        if self.driveLaserCheck.isChecked():
            drive_laser_current = float(self.driveLaserCurrentLine.text())
        if self.probeLaserCheck.isChecked():
            probe_laser_current = float(self.probeLaserCurrentLine.text())
        if self.customCheck.isChecked():
            custom_text = self.customNameLine.text()
        if self.tempCheck.isChecked():
            self.ch = self.channelBox.currentText()
            self.temp = yield self.tempDevice.read_temp(ch=self.ch)
        if self.dcSignalCheck.isChecked():
            dcSignal = yield self.multimeterDevice.return_last_reading()
            dcSignal = dcSignal*1000
        if self.opticoolControlTempCheck.isChecked() and self.opticoolDevice is not None:
            self.opticool_control_temp, _ = self.opticoolDevice.get_temperature(thermometer='control')
        if self.opticoolAuxTempCheck.isChecked() and self.opticoolDevice is not None:
            self.opticool_aux_temp, _ = self.opticoolDevice.get_temperature(thermometer='aux')
        if self.opticoolMagnetCheck.isChecked() and self.opticoolDevice is not None:
            self.opticool_field, _ = self.opticoolDevice.get_field()

        IF_bandwidth = yield self.vnaDevice.IF_bandwidth()
        vna_power    = yield self.vnaDevice.output_power()
        ave_factor   = yield self.vnaDevice.averaging_factor()
        ave_state    = yield self.vnaDevice.averaging_state()
        ave_state = int(ave_state.strip())
        if ave_state == 0:
            ave_state = 'OFF'
        else:
            ave_state = 'ON'
        
        meta_data_dict = {'custom text':custom_text,
                          'drive laser current (mA)':drive_laser_current, 'probe laser current (mA)':probe_laser_current,
                          'IF bandwidth (Hz)':IF_bandwidth, 'Averaging?':ave_state, 'Averaging factor':ave_factor, 'VNA power (dBm)':vna_power,
                          'External Temperature (K)':self.temp, 'Probe laser DC signal (mV)':dcSignal, 'time (s)': time(),
                          'OptiCool control temperature (K)':self.opticool_control_temp,
                          'OptiCool aux temperature (K)':self.opticool_aux_temp,
                          'OptiCool field (T)':self.opticool_field}
        return meta_data_dict
    
    @inlineCallbacks
    def adjust_sweep_range (self, c=None):
        last_fit  = self.parent.resonanceDetectorWindow.initial_guess
        # initial_guess is None, always if we don't use any old value as initial guess but instead just try to fit the entire data range
        # i.e. # interpolation is 0 in resonance detector
        # otherwise it might be None at the beginning, if we don't have autosave on in the resonance detector
        if last_fit is None:
            last_fit = self.parent.resonanceDetectorWindow.last_fit_value
        
        last_fit = np.array(last_fit)
        center_list = last_fit[:,0]
        num_width   = float(self.numGammaLine.text())
        span_list   = 2*last_fit[:,1] * num_width
        num_points = yield self.vnaDevice.num_frequency_points()
        num_point_list = np.ones(len(center_list)) * num_points/len(center_list)
        num_point_list = num_point_list.astype(int)
        
        if len(center_list) == 1:
            yield self.vnaDevice.frequency_range([center_list[0]-span_list[0]/2, center_list[0]+span_list[0]/2])
            yield self.vnaDevice.sweep_type('LIN')
            yield self.parent.vnaMonitorWindow.read_all_params()
        else:
            yield self.vnaDevice.edit_segment_table(center_list, span_list, num_point_list)
            yield self.vnaDevice.sweep_type('SEGM')

    
    def check_auto_stop (self, current_temp):
        stop = False
        if self.minTempBox.isChecked():
            if current_temp<float(self.minTempLine.text()):
                stop = True
        if self.maxTempBox.isChecked():
            if current_temp>float(self.maxTempLine.text()):
                stop = True
        return stop
    
    @inlineCallbacks
    def autosave (self, c=None):
        if self.saveOptionBox.currentText() == 'save every ... seconds':
            while self.autosaving:
                try:
                    self.f, self.X, self.Y          = yield self.vnaDevice.read_trace()
                    save_dict                       = yield self.collect_meta_data()
                    save_dict['freq (Hz)']          = self.f
                    save_dict['Real part (V)']      = self.X
                    save_dict['Imaginary part (V)'] = self.Y
                    
                    path = self.create_save_path()
                    np.savez_compressed(path, **save_dict)
                    if self.check_auto_stop(self.temp):
                        yield self.auto_save_button_clicked()
                except Exception as e:
                    print('Error saving data every ... seconds ...')
                yield self.sleep(float(self.saveIntervalLine.text()))
            return 1
        
        else: # this is the mode where we have individual "single" scans
            # self.vnaDevice.toggle_ave_trigger(state='OFF')
            self.vnaDevice.abort_sweeping()
            if self.autoTrackBox.isChecked():
            # this is the mode where we scan around each resonance and
            # and adjust the range when the resonance frequency changes
                try:
                    yield self.adjust_sweep_range()
                except Exception as e:
                    print('Error setting new frequency range based on last fit ...')
                    print(e)
            if self.autoAlignBox.isChecked():
            # move the laser spot back to where it was originally
                try:
                    # distance between current camera image and reference image
                    translation = yield self.parent.cameraWindow.move_to_reference()
                    current_distance = np.sqrt(translation[0]**2 + translation[1]**2)
                    threshold_distance = float(self.distThresholdLine.text())
                    while current_distance>threshold_distance:
                        translation = yield self.parent.cameraWindow.move_to_reference()
                        current_distance = np.sqrt(translation[0]**2 + translation[1]**2)
                except Exception as e:
                    print('Error aligning to reference image ...')
                    print(e)
            yield self.vnaDevice.start_single_measurement()
            
            scan_bool = False
            while self.autosaving:
                if scan_bool:
                    
                    try:                        
                        save_dict                       = yield self.collect_meta_data()
                        self.f, self.X, self.Y          = yield self.vnaDevice.read_trace()
                        save_dict['freq (Hz)']          = self.f
                        save_dict['Real part (V)']      = self.X
                        save_dict['Imaginary part (V)'] = self.Y
            
                        path = self.create_save_path()
                        np.savez_compressed(path, **save_dict)
                        if self.check_auto_stop(self.temp):
                            yield self.auto_save_button_clicked()
                        
                        if self.autoAlignBox.isChecked():
                        # move the laser spot back to where it was originally
                            try:
                                # distance between current camera image and reference image
                                translation = yield self.parent.cameraWindow.move_to_reference()
                                current_distance = np.sqrt(translation[0]**2 + translation[1]**2)
                                threshold_distance = float(self.distThresholdLine.text())
                                while current_distance>threshold_distance:
                                    translation = yield self.parent.cameraWindow.move_to_reference()
                                    current_distance = np.sqrt(translation[0]**2 + translation[1]**2)
                            except Exception as e:
                                print('Error aligning to reference image ...')
                                print(e)
                        
                        # adjust sweep range
                        # do this after moving the stage
                        # it might be that the current data has already been fitted and you get the most accurate range
                        if self.autoTrackBox.isChecked():
                            try:
                                yield self.adjust_sweep_range()
                            except Exception as e:
                                print('Error setting new frequency range based on last fit ...')
                                print(e)

                        yield self.vnaDevice.start_single_measurement()
                        
                    except Exception as e:
                        print('Error saving data once scan is finished ...')
                        print(e)
                yield self.sleep(0.5)
                scan_bool = yield self.vnaDevice.is_scan_done()
            return 1



    
    #async sleep function - GUI is operable while function sleeps
    def sleep(self, secs):
        d = Deferred()
        self.reactor.callLater(secs,d.callback,'Sleeping')
        return d





if __name__ == '__main__':
    app = QApplication([])
    win = Sweeper()
    win.show()
    app.exec()