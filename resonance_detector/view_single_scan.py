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
from Resonating_Membranes.resonance_detector.load_frequency_sweep import FreqSweepData, FreqSweep
from Resonating_Membranes.resonance_detector.fit_resonances import FitResonances
import numpy as np
import threading
from time import time
from datetime import datetime
import os
import sys
from copy import deepcopy
import ctypes
import json
from numpy.polynomial import polynomial
import platform


class ResonanceDetector (QMainWindow):
    # the signal needs to be defined as a "class-level" attribute, so here, outside of __init__
    autoUpdateWidgetsSignal = pyqtSignal(int)
    def __init__(self, operating_system=None):#, parent=None):
        super(ResonanceDetector, self).__init__()
        
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
        temp[-1] = 'view_single_scan.ui'
        temp_ui     = self.separator.join(temp)
        uic.loadUi(temp_ui, self)

        # load window icon (only works on windows though ...)
        if self.operating_system in ['windows', 'Windows']:
            myappid = u'ResMem.ResonanceDetector'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            temp[-1] = 'resonance_logo.png'
            logo_path = self.separator.join(temp)
            icon = QIcon(logo_path)
            self.setWindowIcon(icon)

        # self.parent = parent

        temp[-1]         = 'config_plotter.json'
        self.config_path = self.separator.join(temp)
        with open(self.config_path, 'r') as openfile:
            self.config = json.load(openfile)

        self.initialize_directory_widgets()
        self.create_band_pass_widgets()
        self.create_individual_sweep_plot()

    def initialize_directory_widgets(self):
        # Widgets and Variables for loading files
        self.current_file_index = 0
        self.fileDialog = QFileDialog()
        self.browseButton.clicked.connect(self.browse_button_clicked)
        self.plotterDir = None
        self.fileList.doubleClicked.connect(lambda: self.fileListDoubleClicked(rescale_axes=True))
       
    def create_band_pass_widgets(self):
        # variables to store the upper and lower cutoff for the bandpass filter of the sweep currently shown
        self.nyq_low  = self.config["BandPass Filter Params"]["lower cutoff"]
        self.nyq_high = self.config["BandPass Filter Params"]["upper cutoff"]
        self.nyqLowLine.setText(str(self.nyq_low))
        self.nyqHighLine.setText(str(self.nyq_high))
        self.updateBandPassParams.clicked.connect(self.update_bandpass_params)
        self.nyqLowLine.textEdited.connect(self.update_nyq_lines)
        self.nyqHighLine.textEdited.connect(self.update_nyq_lines)
        if self.filtBoolcomboBox.currentText() == 'raw':
            self.filtered_bool = False
        elif self.filtBoolcomboBox.currentText() == 'filtered':
            self.filtered_bool = True
        self.filtBoolcomboBox.currentIndexChanged.connect(self.change_filtered_bool)
        
    def create_individual_sweep_plot (self):
        legend_item = self.individualSweepPlot.addLegend(frame=False, labelTextColor='w', labelTextSize='14pt')

        self.freq_sweep_plot_X = pg.ScatterPlotItem([],[], symbol='o')
        color = 'r'
        self.freq_sweep_plot_X.setPen(pg.mkPen(color))
        self.freq_sweep_plot_X.setBrush(pg.mkBrush(color))
        self.individualSweepPlot.addItem(self.freq_sweep_plot_X)
        legend_item.addItem(self.freq_sweep_plot_X, name='Real')
        
        self.freq_sweep_plot_Y = pg.ScatterPlotItem([],[], symbol='d')
        color = 'b'
        self.freq_sweep_plot_Y.setPen(pg.mkPen(color))
        self.freq_sweep_plot_Y.setBrush(pg.mkBrush(color))
        self.individualSweepPlot.addItem(self.freq_sweep_plot_Y)
        legend_item.addItem(self.freq_sweep_plot_Y, name='Imaginary')

        self.individualSweepPlot.showAxis('top', show=True)
        self.individualSweepPlot.showAxis('right', show=True)
        self.individualSweepPlot.getAxis('top').setStyle(showValues=False)
        self.individualSweepPlot.getAxis('right').setStyle(showValues=False)
        self.individualSweepPlot.setLabel('left', 'Signal', units='V', **{'color': '#FFF', 'font-size': '12pt'})
        self.individualSweepPlot.setLabel('bottom', 'Frequency', units='Hz', **{'color': '#FFF', 'font-size': '12pt'})

    # changes here
    def get_filenames_from_folder (self, folder):
        dir_list = os.listdir(folder)
        dir_list = np.array([f'{folder}{self.separator}{name}' for name in dir_list if name.endswith('.dat') or name.endswith('.npz')], dtype=str)
        
        file_creation_times = np.array([os.path.getmtime(name) for name in dir_list])
        filenames = dir_list[np.argsort(file_creation_times)]
        return filenames
    
    def browse_button_clicked (self, plot_dir=None):
        # this is just so that in case someone presses the browse button while the autorefresh is on, it will turn it off
        # if self.autorefresh_enabled:
        #     self.toggleAutorefresh()
        self.fileList.clear()
        # self.xAxisBox.clear()
        self.all_results = None
        try:
            if plot_dir is None or not plot_dir:
                plot_dir = self.fileDialog.getExistingDirectory(self, "Select Directory")
            if plot_dir:
                self.plotterDir = plot_dir
                self.direcotry_print.setText(self.plotterDir)
                self.filenames    = self.get_filenames_from_folder(self.plotterDir)

                for idx, filename in enumerate(self.filenames):
                    temp = filename.split(self.separator)
                    self.fileList.addItem(temp[-1])

        except Exception as e:
            print("Error loading data ...")
            print(e)

    def updateFreqSweepPlot (self, freq_data, X_data, Y_data, title=None, rescale_axes=False):
        if not title is None:
            self.individualSweepPlot.setTitle(title, **{'color': '#FFF', 'size': '12pt'})
        self.freq_sweep_plot_X.setData(freq_data, X_data)
        self.freq_sweep_plot_Y.setData(freq_data, Y_data)
        if rescale_axes:
            self.individualSweepPlot.setXRange(min(freq_data), max(freq_data))
            self.individualSweepPlot.setYRange(min([min(X_data), min(Y_data)]), max([max(X_data), max(Y_data)]))

    def get_freq_sweep (self, filename, nyq_low, nyq_high):
        # pretty much if there is already an error when importing the file
        # it will move the file to a "bad_files" folder in the same directory;
        # if not then "auto_update" will always have a discrepancy between list of filenames and loaded files
        # it will then be stuck in a loop where it tries to fit all files from scratch
        try:
            freqsweep = FreqSweep(filename, nyq_low, nyq_high)
            return freqsweep
        except Exception as e:
            print('Error loading frequency sweep ...')
            print(e)
            print("removed file from list and moved filed to 'bad_files' folder")
            badfiles_directory = filename.split(self.separator)
            badfiles_directory[-1] = 'bad_files'
            badfiles_directory = self.separator.join(badfiles_directory)
            os.makedirs(badfiles_directory, exist_ok=True)
            new_filename = f'{badfiles_directory}{self.separator}{filename.split(self.separator)[-1]}'
            os.rename(filename, new_filename)
            return None


    def fileListDoubleClicked(self, rescale_axes=False):
        try:
            self.current_file_index = self.fileList.currentRow()
            self.current_sweep = FreqSweep(self.filenames[self.current_file_index], nyq_low=self.nyq_low, nyq_high=self.nyq_high)

            if self.filtered_bool:
                f, X, Y = self.current_sweep.filt_sweep.freq, self.current_sweep.filt_sweep.X, self.current_sweep.filt_sweep.Y
            else:
                f, X, Y = self.current_sweep.raw_sweep.freq, self.current_sweep.raw_sweep.X, self.current_sweep.raw_sweep.Y
                X = X-X[0]
                Y = Y-Y[0]
            self.updateFreqSweepPlot(f, X, Y, rescale_axes=rescale_axes)

            # write the correct values of bandpass filter parameters in text fields
            self.nyqHighLine.setText(str(self.nyq_high))
            self.nyqLowLine.setText(str(self.nyq_low))
            self.nyqLowLine.setStyleSheet("color: rgb(0, 0, 0); background-color: rgb(255,255,255)")
            self.nyqHighLine.setStyleSheet("color: rgb(0, 0, 0); background-color: rgb(255,255,255)")

            # write the correct values for the scan paramters in their fields
            self.update_scan_params(self.filenames[self.current_file_index])

        except Exception as e:
            print('Error in fileListDoubleClicked ...')
            print(e)

    def update_bandpass_params(self):
        nyq_low_text  = self.nyqLowLine.text()
        nyq_high_text = self.nyqHighLine.text()
        try:
            self.nyq_low  = float(nyq_low_text)
            self.config["BandPass Filter Params"]["lower cutoff"] = self.nyq_low
            self.nyq_high = float(nyq_high_text)
            self.config["BandPass Filter Params"]["upper cutoff"] = self.nyq_high

            self.nyqLowLine.setStyleSheet("color: rgb(0, 0, 0); background-color: rgb(255,255,255)")
            self.nyqHighLine.setStyleSheet("color: rgb(0, 0, 0); background-color: rgb(255,255,255)")

            with open(self.config_path, "w") as outfile:
                json.dump(self.config, outfile, indent=4)

            try:
                filename_temp = self.filenames[self.current_file_index]
                self.current_sweep = FreqSweep(filename_temp, nyq_low=self.nyq_low, nyq_high=self.nyq_high)
                if self.filtered_bool:
                    freq_data, X_data, Y_data = self.current_sweep.filt_sweep.freq, self.current_sweep.filt_sweep.X, self.current_sweep.filt_sweep.Y
                else:
                    freq_data, X_data, Y_data = self.current_sweep.raw_sweep.freq, self.current_sweep.raw_sweep.X, self.current_sweep.raw_sweep.Y
                    X_data = X_data - X_data[0]
                    Y_data = Y_data - Y_data[0]
                self.updateFreqSweepPlot(freq_data, X_data, Y_data, rescale_axes=False)
            except Exception as e:
                print('bandpass parameters were updated, but error plotting data')
                print(e)
            
        except Exception as e:
            print("Error updating bandpass parameters ...")
            print(e)

    
    def update_nyq_lines(self):
        self.nyqLowLine.setStyleSheet("color: rgb(255,0,0); background-color: rgb(255,255,255)")
        self.nyqHighLine.setStyleSheet("color: rgb(255,0,0); background-color: rgb(255,255,255)")

    def change_filtered_bool (self):
        try:
            if self.filtBoolcomboBox.currentText() == 'filtered':
                self.filtered_bool = True
                f, X, Y = self.current_sweep.filt_sweep.freq, self.current_sweep.filt_sweep.X, self.current_sweep.filt_sweep.Y
            elif self.filtBoolcomboBox.currentText() == 'raw':
                self.filtered_bool = False
                f, X, Y = self.current_sweep.raw_sweep.freq, self.current_sweep.raw_sweep.X, self.current_sweep.raw_sweep.Y
                X = X-X[0]
                Y = Y-Y[0]
            self.updateFreqSweepPlot(f, X, Y, rescale_axes=True)
        except Exception as e:
            print('Error in change_filtered_bool ...')
            print(e)
            
    def update_scan_params (self, filename):
        dat = np.load(filename)
        line_edits = [self.tempEdit, self.driveEdit, self.probeEdit, self.ifEdit, self.powerEdit, self.dcEdit]
        for ii, key in enumerate(['Temperature (K)','drive laser current (mA)','probe laser current (mA)','IF bandwidth (Hz)','VNA power (dBm)','Probe laser DC signal (mV)']):
            try:
                temp = float(dat[key])
                temp = np.round(temp, 1)
                line_edits[ii].setText(f'{temp}')
            except Exception as e:
                line_edits[ii].setText('')


if __name__ == '__main__':
    QApplication.setStyle('Fusion')
    app = QApplication([])
    app.setStyle('Windows')
    win = ResonanceDetector()
    win.show()
    app.exec()