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
from time import time
import os
import sys
from copy import deepcopy
import ctypes
import platform
import twisted
from twisted.internet.defer import inlineCallbacks, Deferred


class DataViewer (QMainWindow):
    def __init__(self, reactor, parent=None, operating_system=None):
        super(DataViewer, self).__init__()

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
        temp[-1] = 'data_view.ui'
        temp_ui     = self.separator.join(temp)
        uic.loadUi(temp_ui, self)

        # load window icon (only works on windows though ...)
        if self.operating_system in ['windows', 'Windows']:
            myappid = u'Resistivity.data_view'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            temp[-1] = 'data_view_logo.png'
            logo_path = self.separator.join(temp)
            icon = QIcon(logo_path)
            self.setWindowIcon(icon)

        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.parent  = parent
        self.reactor = reactor

        self.updateInterval = 2
        self.intervalLine.setText('2')

        self.initialize_plot()
        self.populate_x_axis_combo()
        self.xCheck.stateChanged.connect(lambda b, plot_item=self.X_plot, label='X (V)', checkbox=self.xCheck : self.change_legend(plot_item, label, checkbox))
        self.yCheck.stateChanged.connect(lambda b, plot_item=self.Y_plot, label='Y (V)', checkbox=self.yCheck : self.change_legend(plot_item, label, checkbox))
        self.ampCheck.stateChanged.connect(lambda b, plot_item=self.amp_plot, label='Amp (V)', checkbox=self.ampCheck : self.change_legend(plot_item, label, checkbox))
        self.phiCheck.stateChanged.connect(lambda b, plot_item=self.phi_plot, label='Phase (deg)', checkbox=self.phiCheck : self.change_legend(plot_item, label, checkbox))

    def populate_x_axis_combo(self):
        if self.parent is None:
            return
        items_to_add = [
            (self.parent.chACheck,                 'Temp. Ch. A (K)'),
            (self.parent.chBCheck,                 'Temp. Ch. B (K)'),
            (self.parent.opticoolControlTempCheck, 'OptiCool Contr. Temp. (K)'),
            (self.parent.opticoolAuxTempCheck,     'OptiCool Aux. Temp. (K)'),
            (self.parent.opticoolMagnetCheck,      'OptiCool Magn. Field (T)'),
        ]
        for checkbox, label in items_to_add:
            if checkbox.isChecked():
                self.comboBox.addItem(label)
            checkbox.toggled.connect(lambda checked, s=label: self.toggle_x_axis_item(checked, s))

    def toggle_x_axis_item(self, checked, label):
        if checked:
            self.comboBox.addItem(label)
        else:
            idx = self.comboBox.findText(label)
            if idx >= 0:
                self.comboBox.removeItem(idx)

    def initialize_plot (self):
        self.monitorPlot.showAxis('top', show=True)
        self.monitorPlot.showAxis('right', show=True)
        self.monitorPlot.getAxis('top').setStyle(showValues=False)
        self.monitorPlot.getAxis('right').setStyle(showValues=False)

        self.monitorPlot.setLabel('bottom', 'time', units='s', **{'color': '#FFF', 'font-size': '12pt'})
        self.monitorPlot.setLabel('left', 'signal', **{'color': '#FFF', 'font-size': '12pt'})
        self.legend_item = self.monitorPlot.addLegend(frame=False, labelTextColor='w', labelTextSize='14pt')

        self.X_plot = pg.PlotCurveItem([], [], symbol='o')
        color = 'purple'
        self.X_plot.setPen(pg.mkPen(color))
        self.X_plot.setBrush(pg.mkBrush(color))
        self.monitorPlot.addItem(self.X_plot)

        self.Y_plot = pg.PlotCurveItem([], [], symbol='o')
        color = 'red'
        self.Y_plot.setPen(pg.mkPen(color))
        self.Y_plot.setBrush(pg.mkBrush(color))
        self.monitorPlot.addItem(self.Y_plot)

        self.amp_plot = pg.PlotCurveItem([], [], symbol='o')
        color = 'orange'
        self.amp_plot.setPen(pg.mkPen(color))
        self.amp_plot.setBrush(pg.mkBrush(color))
        self.monitorPlot.addItem(self.amp_plot)
        self.legend_item.addItem(self.amp_plot, name='Amp (V)')

        self.phi_plot = pg.PlotCurveItem([], [], symbol='o')
        color = 'blue'
        self.phi_plot.setPen(pg.mkPen(color))
        self.phi_plot.setBrush(pg.mkBrush(color))
        self.monitorPlot.addItem(self.phi_plot)

    def get_x_data(self):
        selected = self.comboBox.currentText()
        if selected == 'Temp. Ch. A (K)':
            self.monitorPlot.setLabel('bottom', 'temperature', units='K', **{'color': '#FFF', 'font-size': '12pt'})
            return self.parent.tempA
        elif selected == 'Temp. Ch. B (K)':
            self.monitorPlot.setLabel('bottom', 'temperature', units='K', **{'color': '#FFF', 'font-size': '12pt'})
            return self.parent.tempB
        elif selected == 'OptiCool Contr. Temp. (K)':
            self.monitorPlot.setLabel('bottom', 'temperature', units='K', **{'color': '#FFF', 'font-size': '12pt'})
            return self.parent.opticool_control_temp_arr
        elif selected == 'OptiCool Aux. Temp. (K)':
            self.monitorPlot.setLabel('bottom', 'temperature', units='K', **{'color': '#FFF', 'font-size': '12pt'})
            return self.parent.opticool_aux_temp_arr
        elif selected == 'OptiCool Magn. Field (T)':
            self.monitorPlot.setLabel('bottom', 'field', units='T', **{'color': '#FFF', 'font-size': '12pt'})
            return self.parent.opticool_field_arr
        else:  # 'time'
            self.monitorPlot.setLabel('bottom', 'time', units='s', **{'color': '#FFF', 'font-size': '12pt'})
            return self.parent.time

    def change_legend (self, plot_item, label, checkbox):
        if checkbox.isChecked():
            self.legend_item.addItem(plot_item, name=label)
        else:
            self.legend_item.removeItem(plot_item)

    @inlineCallbacks
    def monitor (self, c=None):
        self.plotting = True
        while self.plotting:
            try:
                x_data = self.get_x_data()

                if self.xCheck.isChecked():
                    self.X_plot.setData(x_data, self.parent.X)
                else:
                    self.X_plot.setData([],[])

                if self.yCheck.isChecked():
                    self.Y_plot.setData(x_data, self.parent.Y)
                else:
                    self.Y_plot.setData([],[])

                if self.ampCheck.isChecked():
                    self.amp_plot.setData(x_data, self.parent.amp)
                else:
                    self.amp_plot.setData([],[])

                if self.phiCheck.isChecked():
                    self.phi_plot.setData(x_data, self.parent.phi)
                else:
                    self.phi_plot.setData([],[])

            except Exception as e:
                print('Error updating plot ...')
                print(e)

            # this is just in case someone wasn't quick enough to type in a correct number
            # when it tries to read it
            intervalText = self.intervalLine.text()
            try:
                temp = float(intervalText)
                if temp > 0:
                    self.updateInterval = temp
            except Exception as e:
                print('error updating interval ...')
                print(f'keep old interval of {self.updateInterval} seconds')
                print(e)
            yield self.sleep(self.updateInterval)

    #async sleep function - GUI is operable while function sleeps
    def sleep(self, secs):
        d = Deferred()
        self.reactor.callLater(secs,d.callback,'Sleeping')
        return d

    def closeEvent(self, e):
        self.plotting=False



if __name__ == '__main__':
    app = QApplication([])
    win = Monitor()
    win.show()
    app.exec()
