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
from RDS_measure.resistivity_sweeper.data_view import DataViewer
from datetime import datetime


class RhoSweeper (QMainWindow):
    def __init__(self, reactor, parent=None, operating_system=None):
        super(RhoSweeper, self).__init__()

        self.operating_system = operating_system
        if operating_system is None:
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
        temp[-1] = 'resistivity_sweeper.ui'
        temp_ui     = self.separator.join(temp)
        uic.loadUi(temp_ui, self)

        # load window icon (only works on windows though ...)
        if self.operating_system in ['windows', 'Windows']:
            myappid = u'Resistivity.Sweeper'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            temp[-1] = 'resistivity_logo.png'
            logo_path = self.separator.join(temp)
            icon = QIcon(logo_path)
            self.setWindowIcon(icon)

        self.parent  = parent
        self.reactor = reactor
        self.opticoolDevice = None
        if self.parent is not None:
            self.lockinDevice = self.parent.deviceDict['lockin']
            self.tempDevice = self.parent.deviceDict['temperature']
            self.opticoolDevice = self.parent.deviceDict['opticool']
        self.X, self.Y, self.amp, self.phi = np.array([]), np.array([]), np.array([]), np.array([])
        self.tempA = np.array([])
        self.tempB = np.array([])
        self.opticool_control_temp_arr = np.array([])
        self.opticool_aux_temp_arr = np.array([])
        self.opticool_field_arr = np.array([])
        self.time, self.date = np.array([]), np.array([])
        self.current_tempA = 0
        self.current_tempB = 0
        self.opticool_control_temp = 0
        self.opticool_aux_temp = 0
        self.opticool_field = 0

        self.initialize_directory_widgets()
        self.initialize_auto_save_widgets()

        # Connect the close event to the custom function
        self.resistivityPlotWindow = None
        self.closeEvent = self.on_close_event

    def update_device_dict (self):
        self.tempDevice = self.parent.deviceDict['temperature']
        self.lockinDevice = self.parent.deviceDict['lockin']
        self.opticoolDevice = self.parent.deviceDict['opticool']

    def initialize_directory_widgets (self):
        self.save_name = None
        self.fileDialog = QFileDialog()
        self.browseButton.clicked.connect(self.browse_button_clicked)
        return

    def initialize_auto_save_widgets(self):
        self.autosaving = False
        self.autoSaveButton.setStyleSheet("QPushButton#autoSaveButton {color: rgb(0, 255, 0);background-color:rgb(0, 0, 0);border: 2px solid rgb(0, 255, 0);border-radius: 5px}")
        self.autoSaveButton.clicked.connect(self.auto_save_button_clicked)
        self.viewDataButton.clicked.connect(self.view_data)

        self.auto_stop_item_map = [
            (self.opticoolControlTempCheck, 'OptiCool Contr. Temp. (K)'),
            (self.opticoolAuxTempCheck,     'OptiCool Aux. Temp. (K)'),
            (self.opticoolMagnetCheck,      'OptiCool Magn. Field (T)'),
            (self.chACheck,                 'Temp. Ch. A (K)'),
            (self.chBCheck,                 'Temp. Ch. B (K)'),
        ]
        for checkbox, item_string in self.auto_stop_item_map:
            if checkbox.isChecked():
                self.autoStopItemBox.addItem(item_string)
            checkbox.toggled.connect(lambda checked, s=item_string: self.toggle_auto_stop_item(checked, s))

    def toggle_auto_stop_item(self, checked, item_string):
        if checked:
            self.autoStopItemBox.addItem(item_string)
        else:
            idx = self.autoStopItemBox.findText(item_string)
            if idx >= 0:
                self.autoStopItemBox.removeItem(idx)

    def browse_button_clicked (self):
        try:
            self.save_name, file_type = self.fileDialog.getSaveFileName(self, "QFileDialog.getOpenFileNames()","","Data File (*.dat)")
            if not self.save_name.endswith('.dat'):
                self.save_name = self.save_name+'.dat'
            self.directoryLine.setText(self.save_name)
        except Exception as e:
            print("Error specifying filename ...")
            print(e)

    def view_data (self):
        self.resistivityPlotWindow = DataViewer(reactor=self.reactor, parent=self)
        self.resistivityPlotWindow.show()
        self.resistivityPlotWindow.monitor()

    @inlineCallbacks
    def auto_save_button_clicked (self, c=None):
        if self.autosaving:
            self.autosaving = False
            self.autoSaveButton.setStyleSheet("QPushButton#autoSaveButton {color: rgb(0, 255, 0);background-color:rgb(0, 0, 0);border: 2px solid rgb(0, 255, 0);border-radius: 5px}")
            self.autoSaveButton.setText('Start')
            self.commentCheck.setEnabled(True)
            self.commentLine.setEnabled(True)
            self.browseButton.setEnabled(True)
            self.directoryLine.setEnabled(True)
            self.chACheck.setEnabled(True)
            self.chBCheck.setEnabled(True)
            self.opticoolControlTempCheck.setEnabled(True)
            self.opticoolAuxTempCheck.setEnabled(True)
            self.opticoolMagnetCheck.setEnabled(True)
        else:
            self.autosaving = True
            self.autoSaveButton.setStyleSheet("QPushButton#autoSaveButton {color: rgb(255, 0, 0);background-color:rgb(0, 0, 0);border: 2px solid rgb(255, 0, 0);border-radius: 5px}")
            self.autoSaveButton.setText('Stop')
            self.commentCheck.setEnabled(False)
            self.commentLine.setEnabled(False)
            self.browseButton.setEnabled(False)
            self.directoryLine.setEnabled(False)
            self.chACheck.setEnabled(False)
            self.chBCheck.setEnabled(False)
            self.opticoolControlTempCheck.setEnabled(False)
            self.opticoolAuxTempCheck.setEnabled(False)
            self.opticoolMagnetCheck.setEnabled(False)
            yield self.autosave()
        return 1

    @inlineCallbacks
    def create_file_header (self, c=None):
        try:
            freq = yield self.lockinDevice.oscillator_frequency()
            amp  = yield self.lockinDevice.oscillator_voltage()
            TC   = yield self.lockinDevice.time_constant()
            gain = yield self.lockinDevice.AC_gain()
            sensitivity = yield self.lockinDevice.voltage_sensitivity()
            header = f'frequency (Hz): {freq}'
            header+= f'\namplitude (Vrms): {amp}'
            header+= f'\ntime constant (s): {TC}'
            header+= f'\nAC gain (dB): {gain}'
            header+= f'\nvoltage sensitivity (V): {sensitivity}'
            if self.commentCheck.isChecked():
                comment = self.commentLine.text()
                header += '\n'+comment
            header+= yield '\n'
            header += 'timestamp y-m-d h:m:s,'
            header += 'time (s),'
            if self.chACheck.isChecked():
                header += 'temperature A (K),'
            if self.chBCheck.isChecked():
                header += 'temperature B (K),'
            if self.opticoolControlTempCheck.isChecked():
                header += 'OptiCool control temp (K),'
            if self.opticoolAuxTempCheck.isChecked():
                header += 'OptiCool aux temp (K),'
            if self.opticoolMagnetCheck.isChecked():
                header += 'OptiCool field (T),'
            header += 'X (V),'
            header += 'Y (V),'
            header += 'amplitude (V),'
            header += 'phase (degrees)'
            return header
        except Exception as e:
            print('Error creating file header ...')
            print(e)

    def check_auto_stop(self):
        stop = False
        if self.autoStopCheckBox.isChecked():
            relation  = self.relationBox.currentText()
            threshold = float(self.thresholdLine.text().strip())
            current_item = self.autoStopItemBox.currentText()
            if current_item == 'OptiCool Aux. Temp. (K)':
                current_value = self.opticool_aux_temp
            elif current_item == 'OptiCool Contr. Temp. (K)':
                current_value = self.opticool_control_temp
            elif current_item == 'OptiCool Magn. Field (T)':
                current_value = self.opticool_field
            elif current_item == 'Temp. Ch. A (K)':
                current_value = self.current_tempA
            else:
                current_value = self.current_tempB
            if relation == '>':
                if current_value > threshold:
                    stop = True
            else:
                if current_value < threshold:
                    stop = True
        return stop

    @inlineCallbacks
    def autosave (self, c=None):
        if self.save_name is not self.directoryLine.text():
            self.save_name = self.directoryLine.text()
            if not self.save_name.endswith('.dat'):
                self.save_name = self.save_name+'.dat'

        self.X, self.Y, self.amp, self.phi = np.array([]), np.array([]), np.array([]), np.array([])
        self.tempA = np.array([])
        self.tempB = np.array([])
        self.opticool_control_temp_arr = np.array([])
        self.opticool_aux_temp_arr = np.array([])
        self.opticool_field_arr = np.array([])
        self.time, self.date = np.array([]), np.array([])
        header = yield self.create_file_header()
        while self.autosaving:
            try:
                current_date = datetime.today().strftime('%Y-%m-%d %H:%M:%S')
                self.date = np.append(self.date, current_date)
                current_time = time()
                self.time = np.append(self.time, current_time)

                if self.chACheck.isChecked():
                    self.current_tempA = yield self.tempDevice.read_temp(ch='A')
                    self.tempA = np.append(self.tempA, self.current_tempA)
                if self.chBCheck.isChecked():
                    self.current_tempB = yield self.tempDevice.read_temp(ch='B')
                    self.tempB = np.append(self.tempB, self.current_tempB)
                if self.opticoolControlTempCheck.isChecked() and self.opticoolDevice is not None:
                    self.opticool_control_temp, _ = self.opticoolDevice.get_temperature(thermometer='control')
                    self.opticool_control_temp_arr = np.append(self.opticool_control_temp_arr, self.opticool_control_temp)
                if self.opticoolAuxTempCheck.isChecked() and self.opticoolDevice is not None:
                    self.opticool_aux_temp, _ = self.opticoolDevice.get_temperature(thermometer='aux')
                    self.opticool_aux_temp_arr = np.append(self.opticool_aux_temp_arr, self.opticool_aux_temp)
                if self.opticoolMagnetCheck.isChecked() and self.opticoolDevice is not None:
                    self.opticool_field, _ = self.opticoolDevice.get_field()
                    self.opticool_field_arr = np.append(self.opticool_field_arr, self.opticool_field)

                current_X = yield self.lockinDevice.measure_X(check_expand=True)
                self.X   = np.append(self.X, current_X)
                current_Y = yield self.lockinDevice.measure_Y(check_expand=True)
                self.Y   = np.append(self.Y, current_Y)
                current_amp = yield self.lockinDevice.measure_Amp(check_expand=True)
                self.amp = np.append(self.amp, current_amp)
                current_phase = yield self.lockinDevice.measure_Phase()
                self.phi = np.append(self.phi, current_phase)

                cols = [self.date, np.round(self.time-self.time[0],2)]
                if self.chACheck.isChecked():
                    cols.append(self.tempA)
                if self.chBCheck.isChecked():
                    cols.append(self.tempB)
                if self.opticoolControlTempCheck.isChecked():
                    cols.append(self.opticool_control_temp_arr)
                if self.opticoolAuxTempCheck.isChecked():
                    cols.append(self.opticool_aux_temp_arr)
                if self.opticoolMagnetCheck.isChecked():
                    cols.append(self.opticool_field_arr)
                cols.extend([self.X, self.Y, self.amp, self.phi])
                save_data = np.vstack(cols, dtype=str).T
                np.savetxt(self.save_name, save_data, header=header, delimiter=',', fmt='%s')

                if self.check_auto_stop():
                    yield self.auto_save_button_clicked()

                yield self.sleep(float(self.saveIntervalLine.text()))
            except Exception as e:
                print('Error saving data ...')
                print(e)
            yield self.sleep(float(self.saveIntervalLine.text()))
        return 1

    #async sleep function - GUI is operable while function sleeps
    def sleep(self, secs):
        d = Deferred()
        self.reactor.callLater(secs,d.callback,'Sleeping')
        return d

    def on_close_event(self, event):
        if not self.resistivityPlotWindow is None:
            try:
                self.resistivityPlotWindow.close()
                self.resistivityPlotWindow = None
            except:
                self.resistivityPlotWindow = None
        # Call the default closeEvent to close the window
        super().closeEvent(event)





if __name__ == '__main__':
    QApplication.setStyle('Fusion')
    app = QApplication([])
    app.setStyle('Windows')
    import qt5reactor
    qt5reactor.install()
    from twisted.internet import reactor
    win = RhoSweeper(reactor)
    win.show()
    app.exec()
