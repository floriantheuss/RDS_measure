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
from RDS_measure.resonance_detector.load_frequency_sweep import FreqSweepData, FreqSweep
from RDS_measure.resonance_detector.fit_resonances import FitResonances
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
        temp[-1] = 'resonance_detector.ui'
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
        self.initialize_data_and_fit_variables()
        self.create_band_pass_widgets()
        self.create_automated_fit_widgets()
        self.initialize_resonance_list_widgets()
        self.create_individual_sweep_plot()
        self.create_temp_dep_plots()
        self.initialize_auto_update_widgets()

    def initialize_directory_widgets(self):
        # Widgets and Variables for loading files
        self.current_file_index = 0
        self.fileDialog = QFileDialog()
        self.browseButton.clicked.connect(self.browse_button_clicked)
        self.plotterDir = None
        self.fileList.doubleClicked.connect(lambda: self.fileListDoubleClicked(rescale_axes=True))
       
    def initialize_data_and_fit_variables(self):
        # variables to store all data
        self.filenames           = None
        self.temperatures        = None
        # self.times               = None  
        self.sweep_variable_dict = {}

        self.current_sweep = None

        # variables to store fit results
        self.single_fit_result = None # fit results of a single fit
        self.resonances_list   = [] # contains fit results for all resonances shown in "self.ResonancesTable"
        self.all_results       = None # contains fit results for all resonances at all temperatures
        self.last_fit_value    = None # contains the fit values of the most recent fit, but ONLY IF the most recent fit was successful. Otherwise it is the fit before that ...
        self.initial_guess     = None
    
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
        

    def initialize_resonance_list_widgets(self):
        # buttons for single resonance fit and resonance list manipulation
        self.fitSingleLorentzianButton.clicked.connect(self.fit_single_lorentzian)
        self.addResonanceButton.clicked.connect(self.add_resonance_to_table)
        self.updateResonanceButton.clicked.connect(self.update_resonance_in_table)
        self.deleteResonanceButton.clicked.connect(self.remove_resonance_from_table)
        self.saveListButton.clicked.connect(self.save_resonance_list)
        self.makeListNextInitialGuessButton.clicked.connect(self.manually_update_initial_guess)
        self.manual_guess = False
        self.ResonancesTable.doubleClicked.connect(self.resonance_table_double_clicked)
        

    def create_automated_fit_widgets(self):
        self.fit_mult_window          = float(self.config["Automated Fit Params"]["fit mult window"])
        self.num_rep_fits             = int(self.config["Automated Fit Params"]["num repeated fits"])
        self.max_f                    = float(self.config["Automated Fit Params"]["max f (Hz)"])
        self.max_gamma                = float(self.config["Automated Fit Params"]["max gamma (Hz)"])
        self.min_f                    = float(self.config["Automated Fit Params"]["min f (Hz)"])
        self.min_gamma                = float(self.config["Automated Fit Params"]["min gamma (Hz)"])
        self.max_change_f             = float(self.config["Automated Fit Params"]["max change f (Hz)"])
        self.max_change_gamma          = float(self.config["Automated Fit Params"]["max change gamma (Hz)"])
        self.num_extrapolation_points = int(self.config["Automated Fit Params"]["num points for next guess extrapolation"])
        self.multiplicatorWindowLine.setText(str(self.fit_mult_window))
        self.numAutomatedFitsLine.setText(str(self.num_rep_fits))
        self.extrPointsLine.setText(str(self.num_extrapolation_points))

        self.maxfLine.setText(str(self.max_f/1e6))
        self.minfLine.setText(str(self.min_f/1e6))
        self.maxShiftfLine.setText(str(self.max_change_f/1e6))
        self.maxgLine.setText(str(self.max_gamma/1e3))
        self.mingLine.setText(str(self.min_gamma/1e3))
        self.maxShiftgLine.setText(str(self.max_change_gamma/1e3))

        self.updateFitParamsButton.clicked.connect(self.update_fit_params)
        self.multiplicatorWindowLine.textEdited.connect(self.update_fit_params_lines)
        self.maxfLine.textEdited.connect(self.update_fit_params_lines)
        self.minfLine.textEdited.connect(self.update_fit_params_lines)
        self.maxShiftfLine.textEdited.connect(self.update_fit_params_lines)
        self.maxgLine.textEdited.connect(self.update_fit_params_lines)
        self.mingLine.textEdited.connect(self.update_fit_params_lines)
        self.maxShiftgLine.textEdited.connect(self.update_fit_params_lines)
        self.numAutomatedFitsLine.textEdited.connect(self.update_fit_params_lines)
        self.extrPointsLine.textEdited.connect(self.update_fit_params_lines)
        self.FitAllButton.clicked.connect(self.fit_all_button_clicked)
        self.StopFitsButton.clicked.connect(self.stop_fits_button_clicked)
        self.continue_fits = True
        if self.fitDirectionComboBox.currentIndex() == 0:
            self.fit_direction = 1
        elif self.fitDirectionComboBox.currentIndex() == 1:
            self.fit_direction = -1
        self.fitDirectionComboBox.currentIndexChanged.connect(self.change_fit_direction)

    def initialize_auto_update_widgets(self):
        self.autoRefreshTimer = QTimer()
        self.autoRefreshTimer.timeout.connect(self.autorefresh_files)
        self.autoRefreshButton.clicked.connect(self.toggleAutorefresh)
        self.autorefresh_enabled = False
        self.autorefreshThreadRunning = False
        self.updateRateLine.setReadOnly(False)
        self.autoUpdateWidgetsSignal.connect(self.update_individual_sweep_data)
        

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

        self.fit_plot_X = pg.PlotCurveItem([],[])
        self.individualSweepPlot.addItem(self.fit_plot_X)

        self.fit_plot_Y = pg.PlotCurveItem([],[])
        self.individualSweepPlot.addItem(self.fit_plot_Y)

        self.individualSweepPlot.showAxis('top', show=True)
        self.individualSweepPlot.showAxis('right', show=True)
        self.individualSweepPlot.getAxis('top').setStyle(showValues=False)
        self.individualSweepPlot.getAxis('right').setStyle(showValues=False)
        self.individualSweepPlot.setLabel('left', 'Signal', units='V', **{'color': '#FFF', 'font-size': '12pt'})
        self.individualSweepPlot.setLabel('bottom', 'Frequency', units='Hz', **{'color': '#FFF', 'font-size': '12pt'})


    
    def create_temp_dep_plots (self):
        self.saveTempDepButton.clicked.connect(self.save_temp_dep_data)
        self.plotResNumComboBox.currentIndexChanged.connect(self.change_plotted_resonance)

        self.plot_res_num = 0
        self.allSweepsFreqPlot.showAxis('top', show=True)
        self.allSweepsFreqPlot.showAxis('right', show=True)
        self.allSweepsFreqPlot.getAxis('top').setStyle(showValues=False)
        self.allSweepsFreqPlot.getAxis('right').setStyle(showValues=False)
        self.allSweepsFreqPlot.setLabel('left', 'f', units='Hz', **{'color': '#FFF', 'font-size': '10pt'})
        # self.allSweepsFreqPlot.setLabel('bottom', 'Temperature', units='K', **{'color': '#FFF', 'font-size': '10pt'})
        # self.allSweepsFreqPlot.setLabel('bottom', '', units='s')
        self.freq_plot = pg.ScatterPlotItem([],[], symbol='o')
        self.allSweepsFreqPlot.addItem(self.freq_plot)

        self.allSweepsGammaPlot.showAxis('top', show=True)
        self.allSweepsGammaPlot.showAxis('right', show=True)
        self.allSweepsGammaPlot.getAxis('top').setStyle(showValues=False)
        self.allSweepsGammaPlot.getAxis('right').setStyle(showValues=False)
        self.allSweepsGammaPlot.setLabel('left', 'Gamma', units='Hz', **{'color': '#FFF', 'font-size': '10pt'})
        # self.allSweepsGammaPlot.setLabel('bottom', 'Time', units='s', **{'color': '#FFF', 'font-size': '10pt'})
        self.gamma_plot = pg.ScatterPlotItem([],[], symbol='o')
        self.allSweepsGammaPlot.addItem(self.gamma_plot)

        self.temp_dep_plots_timer = QTimer()
        self.temp_dep_plots_timer.timeout.connect(self.update_temp_dep_plots)
        self.temp_dep_plots_timer.start(1000)

    def update_temp_dep_plots(self):
        if not self.all_results is None:
            if len(self.all_results)>0:
                try:
                    ii    = self.plot_res_num
                    dat   = np.array(self.all_results[ii])
                    f     = dat[:,0]
                    gamma = dat[:,1]
                    # time  = time-np.min(time)
                    # power = math.floor(math.log10(abs(value)) / 3)
                    # scaled_value = value / (1000 ** power)

                    x_axis = self.sweep_variable_dict[self.xAxisBox.currentText()]
                    x_axis = x_axis[::self.fit_direction]
                    x_axis = x_axis[:len(f)]
                    self.freq_plot.setData(x_axis, f)
                    self.gamma_plot.setData(x_axis, gamma)
                    # self.allSweepsGammaPlot.setLabel('bottom', 'Time', units='s', **{'color': '#FFF', 'font-size': '10pt'})

                    # if self.xAxisBox.currentText() == 'Time':
                    #     time = self.times[::self.fit_direction]
                    #     time = time[:len(f)]
                    #     self.freq_plot.setData(time-np.min(time), f)
                    #     self.gamma_plot.setData(time-np.min(time), gamma)
                    #     self.allSweepsGammaPlot.setLabel('bottom', 'Time', units='s', **{'color': '#FFF', 'font-size': '10pt'})
                    # elif self.xAxisBox.currentText() == 'Temperature':
                    #     temp  = self.temperatures[::self.fit_direction]
                    #     self.freq_plot.setData(temp[:len(f)], f)
                    #     self.gamma_plot.setData(temp[:len(f)], gamma)
                    #     self.allSweepsGammaPlot.setLabel('bottom', 'Temperature', units='K', **{'color': '#FFF', 'font-size': '10pt'})
                except Exception as e:
                    print('error updating temperature dependent plots ...')
                    print(e)

    def change_plotted_resonance(self):
        self.plot_res_num = self.plotResNumComboBox.currentIndex()
        self.update_temp_dep_plots()

    # changes here
    def get_filenames_from_folder (self, folder):
        dir_list = os.listdir(folder)
        dir_list = np.array([f'{folder}{self.separator}{name}' for name in dir_list if name.endswith('.dat') or name.endswith('.npz')], dtype=str)
        
        file_creation_times = np.array([os.path.getmtime(name) for name in dir_list])
        filenames = dir_list[np.argsort(file_creation_times)]
        return filenames
    
    def get_temp_from_filename (self, path):
        try:
            temp = path.split(self.separator)[-1]
            temp = temp.split('K')[0]
            temp = temp.split('_')[-1]
            temp = float(temp)
        except:
            temp = np.nan
        return temp
    
    def get_time_from_filename(self, filename, read_from_string=True):
        try:
            if read_from_string:
                temp = filename.split(self.separator)[-1]
                temp = temp.split('_')
                year, month, day = temp[0].split('-')
                hour, minute, second = temp[1].split('-')
                time = datetime(int(year), int(month), int(day), int(hour), int(minute), int(second))
                time = time.timestamp()
            else:
                temp = np.load(filename)
                time = float(temp['time (s)'])
        except Exception as e:
            time = np.nan
        return time
    
       
    def browse_button_clicked (self, plot_dir=None):
        # this is just so that in case someone presses the browse button while the autorefresh is on, it will turn it off
        if self.autorefresh_enabled:
            self.toggleAutorefresh()
        self.fileList.clear()
        self.xAxisBox.clear()
        self.all_results = None
        try:
            if plot_dir is None or not plot_dir:
                plot_dir = self.fileDialog.getExistingDirectory(self, "Select Directory")
            if plot_dir:
                self.plotterDir = plot_dir
                self.direcotry_print.setText(self.plotterDir)
                self.filenames    = self.get_filenames_from_folder(self.plotterDir)

                dat = np.load(self.filenames[0])
                if 'time (s)' in dat.files:
                    self.sweep_variable_dict['time (s)'] = np.zeros(len(self.filenames))
                    self.xAxisBox.addItem('time (s)')
                if 'Temperature (K)' in dat.files:
                    self.sweep_variable_dict['Temperature (K)'] = np.zeros(len(self.filenames))
                    self.xAxisBox.addItem('Temperature (K)')
                for key in dat.files:
                    if key in ['drive laser current (mA)','probe laser current (mA)','IF bandwidth (Hz)','VNA power (dBm)','Probe laser DC signal (mV)']:
                        self.sweep_variable_dict[key] = np.zeros(len(self.filenames))
                        self.xAxisBox.addItem(key)
                self.temperatures = np.zeros(len(self.filenames))
                # self.times        = np.zeros(len(self.filenames))
                for idx, filename in enumerate(self.filenames):
                    temp = filename.split(self.separator)
                    self.fileList.addItem(temp[-1])
                    self.temperatures[idx] = self.get_temp_from_filename(filename)
                    # self.times[idx]        = self.get_time_from_filename(filename)
                    temp = np.load(filename)
                    for key in self.sweep_variable_dict:
                        try:
                            self.sweep_variable_dict[key][idx] = float(temp[key])
                        except:
                            self.sweep_variable_dict[key][idx] = np.nan
            
            # populate the bandpass filter fields with the values that were used to load the data
            # self.nyqLowLine.setText(str(self.nyq_low))
            # self.nyqHighLine.setText(str(self.nyq_high))

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
            T_temp = self.temperatures[self.current_file_index]
            title  = f'T = {T_temp} K'
            self.current_sweep = FreqSweep(self.filenames[self.current_file_index], nyq_low=self.nyq_low, nyq_high=self.nyq_high)

            if self.filtered_bool:
                f, X, Y = self.current_sweep.filt_sweep.freq, self.current_sweep.filt_sweep.X, self.current_sweep.filt_sweep.Y
            else:
                f, X, Y = self.current_sweep.raw_sweep.freq, self.current_sweep.raw_sweep.X, self.current_sweep.raw_sweep.Y
                X = X-X[0]
                Y = Y-Y[0]
            self.updateFreqSweepPlot(f, X, Y, title, rescale_axes=rescale_axes)

            # write the correct values of bandpass filter parameters in text fields
            self.nyqHighLine.setText(str(self.nyq_high))
            self.nyqLowLine.setText(str(self.nyq_low))
            self.nyqLowLine.setStyleSheet("color: rgb(0, 0, 0); background-color: rgb(255,255,255)")
            self.nyqHighLine.setStyleSheet("color: rgb(0, 0, 0); background-color: rgb(255,255,255)")

            # remove data for fit of individual Lorentzian
            self.fit_plot_X.setData([],[])
            self.fit_plot_Y.setData([],[])
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

    def update_fit_params(self):
        fit_mult_window_text = self.multiplicatorWindowLine.text()
        num_rep_fits_text    = self.numAutomatedFitsLine.text()
        extr_points_text     = self.extrPointsLine.text()

        max_f_text            = self.maxfLine.text()
        max_gamma_text        = self.maxgLine.text()
        min_f_text            = self.minfLine.text()
        min_gamma_text        = self.mingLine.text()
        max_change_f_text     = self.maxShiftfLine.text()
        max_change_gamma_text = self.maxShiftgLine.text()
        
        try:
            num_rep_fits_text.isdigit() # checking if it is an integer
            self.num_rep_fits = int(num_rep_fits_text)
            self.numAutomatedFitsLine.setStyleSheet("color: rgb(0, 0, 0); background-color: rgb(255,255,255)")
            self.config["Automated Fit Params"]["num repeated fits"] = self.num_rep_fits

            self.fit_mult_window = float(fit_mult_window_text)
            self.multiplicatorWindowLine.setStyleSheet("color: rgb(0, 0, 0); background-color: rgb(255,255,255)")
            self.config["Automated Fit Params"]["fit mult window"] = self.fit_mult_window
        
            self.max_f = float(max_f_text) * 1e6
            self.maxfLine.setStyleSheet("color: rgb(0, 0, 0); background-color: rgb(255,255,255)")
            self.config["Automated Fit Params"]["max f (Hz)"] = self.max_f
  
            self.max_gamma   = float(max_gamma_text) * 1e3
            self.maxgLine.setStyleSheet("color: rgb(0, 0, 0); background-color: rgb(255,255,255)")
            self.config["Automated Fit Params"]["max gamma (Hz)"] = self.max_gamma
        
            self.min_f = float(min_f_text) * 1e6
            self.minfLine.setStyleSheet("color: rgb(0, 0, 0); background-color: rgb(255,255,255)")
            self.config["Automated Fit Params"]["min f (Hz)"] = self.min_f

            self.min_gamma = float(min_gamma_text) * 1e3
            self.mingLine.setStyleSheet("color: rgb(0, 0, 0); background-color: rgb(255,255,255)")
            self.config["Automated Fit Params"]["min gamma (Hz)"] = self.min_gamma

            self.max_change_f = float(max_change_f_text) * 1e6
            self.maxShiftfLine.setStyleSheet("color: rgb(0, 0, 0); background-color: rgb(255,255,255)")
            self.config["Automated Fit Params"]["max change f (Hz)"] = self.max_change_f

            self.max_change_gamma = float(max_change_gamma_text) * 1e3
            self.maxShiftgLine.setStyleSheet("color: rgb(0, 0, 0); background-color: rgb(255,255,255)")
            self.config["Automated Fit Params"]["max change gamma (Hz)"] = self.max_change_gamma

            extr_points_text.isdigit() # checking if it is an integer
            self.num_extrapolation_points = int(extr_points_text)
            self.extrPointsLine.setStyleSheet("color: rgb(0, 0, 0); background-color: rgb(255,255,255)")
            self.config["Automated Fit Params"]["num points for next guess extrapolation"] = self.num_extrapolation_points

            with open(self.config_path, "w") as outfile:
                json.dump(self.config, outfile, indent=4)
        except Exception as e:
            print('error updating the fit parameters ...')
            print(e)
    
    def update_fit_params_lines(self):
        self.multiplicatorWindowLine.setStyleSheet("color: rgb(255,0,0); background-color: rgb(255,255,255)")
        self.numAutomatedFitsLine.setStyleSheet("color: rgb(255,0,0); background-color: rgb(255,255,255)")
        self.extrPointsLine.setStyleSheet("color: rgb(255,0,0); background-color: rgb(255,255,255)")
        self.maxfLine.setStyleSheet("color: rgb(255,0,0); background-color: rgb(255,255,255)")
        self.minfLine.setStyleSheet("color: rgb(255,0,0); background-color: rgb(255,255,255)")
        self.maxShiftfLine.setStyleSheet("color: rgb(255,0,0); background-color: rgb(255,255,255)")
        self.maxgLine.setStyleSheet("color: rgb(255,0,0); background-color: rgb(255,255,255)")
        self.mingLine.setStyleSheet("color: rgb(255,0,0); background-color: rgb(255,255,255)")
        self.maxShiftgLine.setStyleSheet("color: rgb(255,0,0); background-color: rgb(255,255,255)")

    
    def fit_single_lorentzian(self):
        try:
            view_range = self.individualSweepPlot.viewRange()
            freq_range = view_range[0]
            # sweep_temp = self.all_data_list[self.current_file_index]
            # freq, X, Y = sweep_temp.filt_sweep.freq, sweep_temp.filt_sweep.X, sweep_temp.filt_sweep.Y
            if self.filtered_bool:
                freq, X, Y = self.current_sweep.filt_sweep.freq, self.current_sweep.filt_sweep.X, self.current_sweep.filt_sweep.Y
            else:
                freq, X, Y = self.current_sweep.raw_sweep.freq, self.current_sweep.raw_sweep.X, self.current_sweep.raw_sweep.Y
                X, Y = X-X[0], Y-Y[0]
            mask = (freq>=freq_range[0])&(freq<=freq_range[1])
            sweep_mask = FreqSweepData(freq[mask],X[mask], Y[mask])

            f0_guess = np.array([(freq_range[0]+freq_range[1])/2])
            df_guess = np.array([(freq_range[1]-freq_range[0])/2])
            fit = FitResonances(sweep_mask, f0_guess, df_guess, mulitplicator_fit_window=2, number_automated_fits=1)
            self.single_fit_result = fit.fit_individual_Lorentzian()
            f0, gamma, A, phi, c0, c1, m0, m1, f_min_fit, f_max_fit = self.single_fit_result

            self.singleFLine.setText(str(np.round(f0/1e6, 3)))
            self.singleDfLine.setText(str(np.round(gamma/1e3, 2)))
            self.singleQLine.setText(str(np.round(f0/gamma, 2)))

            freq_fit   = np.linspace(f_min_fit, f_max_fit, 1000)
            fit_val = fit.complexLorentzian(freq_fit, f0, gamma, A, phi, c0, c1, m0, m1)
            self.fit_plot_X.setData(freq_fit, np.real(fit_val))
            self.fit_plot_Y.setData(freq_fit, np.imag(fit_val))
        except Exception as e:
            print('Error in fit_single_lorentzian ...')
            print(e)

# here are changes
    def populate_resonance_table_row (self, row_idx, single_fit_result):
        self.ResonancesTable.setItem(row_idx, 0, QTableWidgetItem(f'{np.round(single_fit_result[0]/1e6,3)}')) # changes
        self.ResonancesTable.setItem(row_idx, 1, QTableWidgetItem(f'{np.round(single_fit_result[1]/1e3,2)}')) # changes
        self.ResonancesTable.setItem(row_idx, 2, QTableWidgetItem(f'{np.round(single_fit_result[0]/single_fit_result[1],2)}'))
        self.ResonancesTable.setItem(row_idx, 3, QTableWidgetItem(f'{np.round(single_fit_result[2],5)}'))
        self.ResonancesTable.setItem(row_idx, 4, QTableWidgetItem(f'{np.round(single_fit_result[3],3)}'))
        self.ResonancesTable.setItem(row_idx, 5, QTableWidgetItem(f'{np.round(single_fit_result[4],5)}'))
        self.ResonancesTable.setItem(row_idx, 6, QTableWidgetItem(f'{np.round(single_fit_result[5],5)}'))
        self.ResonancesTable.setItem(row_idx, 7, QTableWidgetItem(f'{np.round(single_fit_result[6],5)}'))
        self.ResonancesTable.setItem(row_idx, 8, QTableWidgetItem(f'{np.round(single_fit_result[7],5)}'))
        self.ResonancesTable.setItem(row_idx, 9, QTableWidgetItem(f'{np.round(single_fit_result[8]/1e6,2)}')) # changes
        self.ResonancesTable.setItem(row_idx,10, QTableWidgetItem(f'{np.round(single_fit_result[9]/1e6,2)}')) # changes


    def add_resonance_to_table (self):
        num_rows = self.ResonancesTable.rowCount()
        try:
            current_row = self.ResonancesTable.currentRow()
            last_row = self.ResonancesTable.rowCount()
            if current_row > -1:
                add_row = current_row+1
            else:
                add_row = last_row
                        
            self.ResonancesTable.insertRow(add_row)
            self.populate_resonance_table_row(add_row, self.single_fit_result)
            self.ResonancesTable.setCurrentCell(add_row, 0)
            self.plotResNumComboBox.addItem(str(self.plotResNumComboBox.count()+1))

            # add to variable containing all resonances
            self.resonances_list.insert(add_row, self.single_fit_result)
        except Exception as e:
            print('error adding resonance to table ...')
            print(e)
            # here I'm checking if I added a resonance by accident, if so I'll remove it
            if num_rows<self.ResonancesTable.rowCount():
                self.ResonancesTable.removeRow(add_row)


    def update_resonance_in_table (self):
        try:
            current_row = self.ResonancesTable.currentRow()
            self.populate_resonance_table_row(current_row, self.single_fit_result)
            # update variable containing all resonances
            self.resonances_list[current_row] = self.single_fit_result
        except Exception as e:
            print('error updating resonance ...')
            print(e)


    def remove_resonance_from_table (self):
        try:
            current_row = self.ResonancesTable.currentRow()
            self.ResonancesTable.removeRow(current_row)
            last_row = self.ResonancesTable.rowCount()-1
            if current_row<=last_row:
                self.ResonancesTable.setCurrentCell(current_row, 0)
            else:
                self.ResonancesTable.setCurrentCell(last_row, 0)
            self.resonances_list.pop(current_row)
            self.plotResNumComboBox.removeItem(self.plotResNumComboBox.count()-1)
        except Exception as e:
            print ('error deleting resonance ...')
            print(e)
    

    def resonance_table_double_clicked (self):
        try:
            # set view of plot window
            current_row = self.ResonancesTable.currentRow()
            f0, gamma, A, phi, c0, c1, m0, m1, fmin, fmax = self.resonances_list[current_row]
            self.individualSweepPlot.setXRange(fmin, fmax)
            # sweep_temp = self.all_data_list[self.current_file_index]
            if self.filtered_bool:
                f, X, Y = self.current_sweep.filt_sweep.freq, self.current_sweep.filt_sweep.X, self.current_sweep.filt_sweep.Y
            else:
                f, X, Y = self.current_sweep.raw_sweep.freq, self.current_sweep.raw_sweep.X, self.current_sweep.raw_sweep.Y
                X, Y = X-X[0], Y-Y[0]
            
            mask = (f>=fmin)&(f<=fmax)
            X = X[mask]
            Y = Y[mask]
            self.individualSweepPlot.setYRange(min([min(X), min(Y)]), max([max(X), max(Y)]))

            # plot the fit you just double clicked
            freq_fit   = np.linspace(fmin, fmax, 1000)
            fit = FitResonances([],[],[])
            fit_val = fit.complexLorentzian(freq_fit, f0, gamma, A, phi, c0, c1, m0, m1)
            self.fit_plot_X.setData(freq_fit, np.real(fit_val))
            self.fit_plot_Y.setData(freq_fit, np.imag(fit_val))
        except Exception as e:
            print('error showing resonance ...')
            print(e)

    def save_resonance_list(self):
        save_name, file_type = self.fileDialog.getSaveFileName(self, "QFileDialog.getOpenFileNames()","","Data File (*.dat)")
        if not save_name.endswith('.dat'):
            save_name = save_name+'.dat'
        try:
            save_data = np.array(self.resonances_list)
            header='f0 (Hz),gamma(Hz),A,phi,c0,c1,m0,m1,fmin(Hz),fmax (Hz)'
            np.savetxt(save_name, save_data, delimiter=',', header=header)
            print('resonance list successfully saved ...')
        except Exception as e:
            print('error saving the resonance list ...')
            print(e)


    def fit_single_data (self, freqsweep, initial_guess, all_results, plot_fits_bool=False, idx=None, temperature=None):
        # fits multiple resonances in one sweep
        # i.e. this is loads one frequency sweep at one temperature (or other sweep variable), but it may contain multiple resonances
        t0 = time()
        if self.filtered_bool:
            fit_data = freqsweep.filt_sweep
        else:
            fit_data = freqsweep.raw_sweep
            fit_data.X = fit_data.X-fit_data.X[0]
            fit_data.Y = fit_data.Y-fit_data.Y[0]

        if initial_guess is None:
            initial_guess  = np.array(self.resonances_list)*0
            dim = len(initial_guess[:,0])
            initial_guess[:,0] = np.ones(dim)*(np.max(fit_data.freq) + np.min(fit_data.freq))/2
            initial_guess[:,1] = np.ones(dim)*(np.max(fit_data.freq) - np.min(fit_data.freq))/2
            # initial_guess[:,2] = np.ones(dim)*np.max(np.abs(fit_data.X+1j*fit_data.Y))
            # print(initial_guess)

        fit = FitResonances(fit_data, 
                            f0_guess_array    =initial_guess[:,0],
                            gamma_guess_array =initial_guess[:,1],
                            A_guess_array     =initial_guess[:,2],
                            phi_guess_array   =initial_guess[:,3],
                            c0_guess_array    =initial_guess[:,4],
                            c1_guess_array    =initial_guess[:,5],
                            m0_guess_array    =initial_guess[:,6],
                            m1_guess_array    =initial_guess[:,7],
                            mulitplicator_fit_window=self.fit_mult_window,
                            number_automated_fits=self.num_rep_fits,
                            plot_fits_bool=plot_fits_bool)
        fit.repeat_multiple_Lorentzians_fit()

        # these are the fit results
        # it contains the results of all resonances at one particular temperature (or other sweep variable)
        fit_results_temp = np.array([fit.f0_array,fit.gamma_array,fit.A_array,fit.phi_array,fit.c0_array,
                                     fit.c1_array,fit.m0_array,fit.m1_array,fit.fmin_array,fit.fmax_array]).T             
                        
        # change the last_value, i.e. start params for new fit, to the most recent fit result
        # if a particular fit wasn't successful the result should be nan
        # so here I am checking if that was the case
        # if so, we use the results from the previous fits as new guess
        idx_unsuccessful = np.array([], dtype=int)
        fit_results_final = deepcopy(self.last_fit_value)
        for kk, resonance in enumerate(fit_results_temp):
            if np.isnan(resonance[0]):
                idx_unsuccessful = np.append(idx_unsuccessful, kk)
                text = 'fit error'
            elif (np.abs(initial_guess[kk,0]-resonance[0])>self.max_change_f) or (resonance[0]<self.min_f) or (resonance[0]>self.max_f):
                idx_unsuccessful = np.append(idx_unsuccessful, kk)
                fit_results_temp[kk] = resonance*np.nan
                text = 'f error'
            elif (np.abs(initial_guess[kk,1]-resonance[1])>self.max_change_gamma) or (resonance[1]<self.min_gamma) or (resonance[1]>self.max_gamma):
                print('intitial gamma guess: ',initial_guess[kk,1])
                print('gamma fit: ',resonance[1])
                print('difference: ', np.abs(initial_guess[kk,1]-resonance[1]))
                print('maximum allowed change: ',self.max_change_gamma)
                print('for debugging also keep in mind limits on max and min value of gamma')
                text = 'gamma error'
                idx_unsuccessful = np.append(idx_unsuccessful, kk)
                fit_results_temp[kk] = resonance*np.nan
            else:
                fit_results_final[kk] = fit_results_temp[kk]

        # append the fit results to a master fit results array
        for kk in np.arange(len(initial_guess[:,0])):
            all_results[kk].append(fit_results_temp[kk])
            

        if idx is None: idx = '-'
        if temperature is None: 
            temp=''
        else:
            temp = f' at {temperature} K'
        if len(idx_unsuccessful) < 1:
            print(f'{idx}: fits{temp} successful in {np.round(time()-t0,3)} seconds')
        else:
            print(f'{idx}: fits {temp} of resonances {idx_unsuccessful} were unsuccessful in {np.round(time()-t0,3)} seconds')
            print('      reason: '+text)
        return fit_results_final
    
    def get_next_initial_guess (self, all_results, num_points):
        if num_points>=2:
            next_guess_list = []
            for ii, item in all_results.items():
                item = np.array(item)
                f = item[:,0]
                mask = np.invert(np.isnan(f))
                item = item[mask]
                if len(item)>=num_points:
                    item = item[-num_points:]

                if len(item)>=2:
                    item_temp = item.T
                    next_guess_temp = np.zeros(len(item_temp))
                    for ii, val in enumerate(item_temp):
                        x   = np.arange(len(val))
                        fit = polynomial.polyfit(x, val, deg=1)
                        next_guess_temp[ii] = polynomial.polyval(max(x)+1, fit)
                    next_guess_list.append(next_guess_temp)
                elif len(item)==1:
                    next_guess_list.append(item[0])
                else:
                    # this case should hopefully never happen
                    # it would mean that no fit was successful
                    # not sure if self.last_fit_value is the bes thing to do here, though
                    # maybe use what is in resonacnes list?
                    next_guess_list.append(self.last_fit_value[ii])
            return np.array(next_guess_list)
        
        elif num_points==1:
            # shouldn't have to do this anymore;
            # self.last_fit_value only gets updated if the new fit is successful
            # so it has the test below already built in
            # for ii, item in all_results.items():
            #     item = np.array(item)
            #     f = item[:,0]
            #     mask = np.invert(np.isnan(f))
            #     item = item[mask]
            #     if len(item)>=1:
            #         next_guess_list.append(item[-1])
            #     else:
            #         # this case should hopefully never happen
            #         # it would mean that no fit was successful
            #         # not sure if self.last_fit_value is the bes thing to do here, though
            #         # maybe use what is in resonacnes list?
            #         next_guess_list.append(self.last_fit_value[ii])
            # return np.array(next_guess_list)
            return self.last_fit_value
        
        elif num_points==0:
            return None
    
    
    def fit_all_data (self, plot_fits_bool=False):
        self.FitAllButton.setEnabled(False)
        self.fitDirectionComboBox.setEnabled(False)
        self.filtBoolcomboBox.setEnabled(False)
        self.autoRefreshButton.setEnabled(False)
        try:
            if self.autorefreshThreadRunning is not True:
                self.autoRefreshButton.setStyleSheet("QPushButton#autoRefreshButton {color: rgb(181,181,181);background-color:rgb(0,0,0);border: 2px solid rgb(181,181,181);border-radius: 5px}")


            self.initial_guess   = np.array(self.resonances_list)
            self.last_fit_value  = deepcopy(self.initial_guess)
            self.all_results     = {ii:[] for ii in np.arange(len(self.initial_guess[:,0]))}
            
            for ii, filename in enumerate(self.filenames[::self.fit_direction]):
                freqsweep = FreqSweep(filename, nyq_low=self.nyq_low, nyq_high=self.nyq_high)
                if self.continue_fits:
                    if self.manual_guess is True:
                        print()
                        print('set new manual initial guess')
                        print(self.initial_guess)
                        print()
                        self.manual_guess = False
                    self.last_fit_value = self.fit_single_data (freqsweep, initial_guess=self.initial_guess, all_results=self.all_results, plot_fits_bool=plot_fits_bool, idx=ii, temperature=self.get_temp_from_filename(filename))
                    self.initial_guess  = self.get_next_initial_guess(self.all_results, self.num_extrapolation_points)
                else:
                    break
        except Exception as e:
            print('error fitting all files ...')
            print(e)
        
        self.autoUpdateWidgetsSignal.emit(len(self.temperatures)-1)
        self.continue_fits = True
        self.FitAllButton.setEnabled(True)
        self.fitDirectionComboBox.setEnabled(True)
        self.filtBoolcomboBox.setEnabled(True)
        self.autoRefreshButton.setEnabled(True)
        if self.autorefreshThreadRunning is not True:
            self.autoRefreshButton.setStyleSheet("QPushButton#autoRefreshButton {color: rgb(0, 255, 0);background-color:rgb(0,0,0);border: 2px solid rgb(0, 255, 0);border-radius: 5px}")
            

    
    def fit_all_button_clicked (self):
        # this is just so that in case someone presses the browse Fit All while the autorefresh is on, it will turn it off
        if self.autorefresh_enabled:
            self.toggleAutorefresh()
        self.continue_fits = True
        try:
            fits_thread = threading.Thread(target=self.fit_all_data)
            fits_thread.start()
        except Exception as e:
            print('error fitting all files ...')
            print(e)
    
    def stop_fits_button_clicked (self):
        self.continue_fits = False

    # changes here
    def save_temp_dep_data(self):
        if not self.all_results is None:
            if len(self.all_results)>0:
                try:
                    save_dir = self.fileDialog.getExistingDirectory(self, "Select Directory")
                    filename_old = 'old'
                    idx = 1
                    for _, item in self.all_results.items():
                        item = np.array(item)
                        temperatures = self.temperatures[::self.fit_direction][:len(item)]
                        # times        = self.times[::self.fit_direction][:len(item)]
                        ['drive laser current (mA)','probe laser current (mA)','IF bandwidth (Hz)','VNA power (dBm)','Temperature (K)','Probe laser DC signal (mV)','time (s)']
                        save_data = np.zeros((item.shape[0],len(self.sweep_variable_dict)+item.shape[1]))

                        # save_data    = np.concatenate((times[:,np.newaxis],temperatures[:, np.newaxis], item), axis=1)
                        ii = 0
                        header=''
                        if 'time (s)' in self.sweep_variable_dict.keys():
                            save_data[:,ii] = self.sweep_variable_dict['time (s)'][::self.fit_direction][:len(item)]
                            header += 'time (s),'
                            ii+=1
                        if 'Temperature (K)' in self.sweep_variable_dict.keys():
                            save_data[:,ii] = self.sweep_variable_dict['Temperature (K)'][::self.fit_direction][:len(item)]
                            header += 'Temperature (K),'
                            ii+=1
                        save_data[:,ii:ii+item.shape[1]] = item
                        header += 'f0 (Hz),gamma (Hz),A,phase,real offset,imaginary offset,real slope, imaginary slope, fit window min (Hz), fit window max (Hz)'
                        ii+=item.shape[1]
                        for key in self.sweep_variable_dict:
                            if key not in ['time (s)','Temperature (K)']:
                                save_data[:,ii] = self.sweep_variable_dict[key][::self.fit_direction][:len(item)]
                                header += ',' + key
                                ii+=1

                        if self.fit_direction==1:
                            freq = str(np.round(item[0,0]/1e6,0))
                            freq = freq.split('.')[0]
                            filename = f'{save_dir}{self.separator}{freq}_MHz.dat'
                        elif self.fit_direction==-1:
                            freq = item[-1,0]
                            kk = 2
                            while np.isnan(freq):
                                freq = item[-kk,0]
                                kk+=1
                            # freq = str(np.round(item[-1,0]/1e3,0))
                            freq = str(np.round(freq/1e6,0))
                            freq = freq.split('.')[0]
                            filename = f'{save_dir}{self.separator}{freq}_MHz_reversed.dat'
                        
                        # make sure there are no duplicate filenames
                        if filename==filename_old:
                            filename = filename.split('.')
                            filename[-2] = filename[-2]+f'_{idx}'
                            filename = '.'.join(filename)
                            idx+=1
                        else:
                            filename_old = deepcopy(filename)
                            idx = 1
                        # header = 'time (s),Temp (K),f0 (Hz),gamma (Hz),A,phase,real offset,imaginary offset,real slope, imaginary slope, fit window min (Hz), fit window max (Hz)'
                        np.savetxt(filename, save_data, header=header, delimiter=',')
                    print('temperature dependent data successfully saved ...')
                except Exception as e:
                    print('error saving temperature dependent data ...')
                    print(e)

    def refresh_files(self):
        self.autorefreshThreadRunning = True
        try:
            filenames_new = self.get_filenames_from_folder(self.plotterDir)
            files_add     = [files for files in filenames_new if files not in self.filenames]
            files_remove  = [files for files in self.filenames if files not in filenames_new]
            # remove obsolete files and all corresponding data
            for file in files_remove:
                # find row of element to delete
                temp = file.split(self.separator)[-1]
                item = self.fileList.findItems(temp, QtCore.Qt.MatchExactly)[0]
                item_row = self.fileList.row(item)
                # delete element at row from fileList, self.filenames, self.temperatures, self.all_data_list
                self.fileList.takeItem(item_row)
                self.filenames     = np.delete(self.filenames, item_row)
                self.temperatures  = np.delete(self.temperatures, item_row)
                # self.times         = np.delete(self.times, item_row)
                for key in self.sweep_variable_dict:
                    self.sweep_variable_dict[key] = np.delete(self.sweep_variable_dict[key], item_row)
                # self.all_data_list.pop(item_row)
                if not self.all_results is None:
                    if len(self.all_results)>0:
                        for key, value in self.all_results.items():
                            value.pop(item_row)
                            self.all_results[key] = value
            filenames_intermediate = self.filenames 
            # add new files and all corresponding data      
            for file in files_add:
                temp = file.split(self.separator)
                file_temp = deepcopy(file)
                freqsweep = self.get_freq_sweep(file_temp, nyq_low=self.nyq_low, nyq_high=self.nyq_high)

                if not freqsweep is None:
                    self.fileList.addItem(temp[-1])
                    self.filenames = np.append(self.filenames, file)
                    self.temperatures = np.append(self.temperatures, self.get_temp_from_filename(file))
                    # self.times        = np.append(self.times, self.get_time_from_filename(file))
                    temp = np.load(file)
                    for key in self.sweep_variable_dict:
                        try:
                            val = float(temp[key])
                        except:
                            val = np.nan
                        self.sweep_variable_dict[key] = np.append(self.sweep_variable_dict[key], val)
                    # self.all_data_list.append(freqsweep)
            # add fits for all new data
            if (not self.all_results is None) and (len(self.all_results)>0) and (len(self.all_results[0])==len(filenames_intermediate)):
                for file in files_add:
                    if self.manual_guess is True:
                        print()
                        print('set new manual initial guess')
                        print(self.initial_guess)
                        print()
                        self.manual_guess = False
                    file_temp = deepcopy(file)
                    freqsweep = self.get_freq_sweep(file_temp, nyq_low=self.nyq_low, nyq_high=self.nyq_high)
                    if not freqsweep is None:
                        self.last_fit_value = self.fit_single_data (freqsweep, self.initial_guess, self.all_results, temperature=self.get_temp_from_filename(file))
                        self.initial_guess = self.get_next_initial_guess(self.all_results, self.num_extrapolation_points)
                # update the individual sweeps plot and resonance list with the most recently imported sweep and fit
                if len(files_add)>0:
                    self.autoUpdateWidgetsSignal.emit(len(self.temperatures)-1)                
            else:
                print('looks like the number of fits are not the same as the number of loaded files ...')
                print('will try to re-run a fit on all current sweeps')
                self.fit_all_data()
            
        except Exception as e:
            print('error refreshing files ...')
            print(e)
        self.autorefreshThreadRunning = False



    def update_individual_sweep_data(self, row_idx):
        if self.all_results is not None:
            # mark last file in files list
            self.fileList.setCurrentRow(row_idx)
            # update plot
            self.fileListDoubleClicked(rescale_axes=False)
            # update resonance list
            for kk, single_fit_result in enumerate(self.last_fit_value):
                self.populate_resonance_table_row (kk, single_fit_result)
                self.resonances_list[kk] = single_fit_result
    
            for kk, val in self.all_results.items():
                if np.isnan(np.array(val)[-1,0]):
                    for col in range(self.ResonancesTable.columnCount()):
                        item = self.ResonancesTable.item(kk, col)
                        item.setBackground(QColor(255, 0, 0))  # Red background color
                else:
                    for col in range(self.ResonancesTable.columnCount()):
                        item = self.ResonancesTable.item(kk, col)
                    item.setBackground(QColor(0, 255, 0))  # Green background color

    def autorefresh_files (self):
        if not self.autorefreshThreadRunning:
            autorefresh_thread = threading.Thread(target=self.refresh_files)
            autorefresh_thread.start()

    def toggleAutorefresh(self):
        if self.autorefresh_enabled:
            self.FitAllButton.setEnabled(True)
            self.autorefresh_enabled = False
            self.autoRefreshTimer.stop()
            self.updateRateLine.setReadOnly(False)
            self.autoRefreshButton.setText("Start Auto-Update")
            self.autoRefreshButton.setStyleSheet("QPushButton#autoRefreshButton {color: rgb(0, 255, 0);background-color:rgb(0,0,0);border: 2px solid rgb(0, 255, 0);border-radius: 5px}")

        else:
            self.FitAllButton.setEnabled(False)
            self.autorefresh_enabled = True
            try:
                update_rate = int(self.updateRateLine.text())
            except:
                print("text in 'update rate' field cannot be converted to int()")
                print("use 2 s as default value")
                update_rate = int(2)
                self.updateRateLine.setText('2')
            self.updateRateLine.setReadOnly(True)
            self.autoRefreshTimer.start(update_rate*1000)
            self.autoRefreshButton.setText("Stop Auto-Update")
            self.autoRefreshButton.setStyleSheet("QPushButton#autoRefreshButton {color: rgb(255, 0, 0);background-color:rgb(0,0,0);border: 2px solid rgb(255, 0, 0);border-radius: 5px}")
    
    def manually_update_initial_guess(self):
        try:
            self.initial_guess = np.array(self.resonances_list)
            self.manual_guess = True
        except Exception as e:
            print('error manually updating the next initial guess for the automated fit ...')
            print(e)

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
            
    
    def change_fit_direction (self):
        if self.fitDirectionComboBox.currentIndex() == 0:
            self.fit_direction = 1
        elif self.fitDirectionComboBox.currentIndex() == 1:
            self.fit_direction = -1





if __name__ == '__main__':
    QApplication.setStyle('Fusion')
    app = QApplication([])
    app.setStyle('Windows')
    win = ResonanceDetector()
    win.show()
    app.exec()