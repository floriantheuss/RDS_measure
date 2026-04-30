from instrumental.drivers.cameras import uc480
import numpy as np
import matplotlib.pyplot as plt
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
import json
from time import time
from copy import deepcopy
import ctypes
import platform
import twisted
from camera_control.align_images import AlignImages
from shared.monitor.monitor import Monitor
from twisted.internet.defer import inlineCallbacks, Deferred


class Camera (QMainWindow):
    def __init__(self, reactor, parent=None, operating_system=None):
        super(Camera, self).__init__()

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
        temp[-1] = 'camera.ui'
        temp_ui     = self.separator.join(temp)
        uic.loadUi(temp_ui, self)

        # load window icon (only works on windows though ...)
        if self.operating_system in ['windows', 'Windows']:
            myappid = u'CamControl.Master'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            temp[-1] = 'camera_logo.png'
            logo_path = self.separator.join(temp)
            icon = QIcon(logo_path)
            self.setWindowIcon(icon)

        # Connect the close event to the custom function
        # self.closeEvent = self.on_close_event

        # import color map lookup table
        temp[-1] = "color_map_lookup.json"
        lookup_table_path = self.separator.join(temp)
        with open(lookup_table_path, 'r') as openfile:
            self.color_map_lookup_table = json.load(openfile)

        self.init_config()
        self.parent  = parent
        self.reactor = reactor
        self.cameraDevice = self.parent.deviceDict['camera']
        self.xStageDevice = self.parent.deviceDict['xstage']
        self.yStageDevice = self.parent.deviceDict['ystage']
        self.zstageDevice = self.parent.deviceDict['zstage']
        self.multimeterDevice = self.parent.deviceDict['multimeter']


        self.initialize_camera_plot_widgets()
        self.initialize_manual_movement_widgets()
        self.initialize_auto_movement_widgets()
        self.initialize_zstage_widgets()

        # Connect the close event to the custom function
        self.closeEvent = self.on_close_event
    
    def update_device_dict (self):
        self.cameraDevice = self.parent.deviceDict['camera']
        self.xStageDevice = self.parent.deviceDict['xstage']
        self.yStageDevice = self.parent.deviceDict['ystage']
        self.zstageDevice = self.parent.deviceDict['zstage']
        self.multimeterDevice = self.parent.deviceDict['multimeter']
        # print(self.cameraDevice)

    def init_config (self):
        # import ui file
        path     = str( Path(__file__).absolute() )
        temp     = path.split(self.separator)

        temp[-1] = 'reference_image.npy'
        self.reference_image_path = self.separator.join(temp)
        try:
            self.init_ref_image = np.load(self.reference_image_path)
        except:
            self.init_ref_image = None

        temp[-1]         = 'config_cameraControl.json'
        self.config_path = self.separator.join(temp)
        with open(self.config_path, 'r') as openfile:
            self.config = json.load(openfile)

        self.laser_pos_x = self.config['laser spot location x (pixel)']
        self.laser_pos_y = self.config['laser spot location y (pixel)']
        self.accelerationBox.setValue(self.config['acceleration (um/s^2)'])
        self.velocityBox.setValue(self.config['velocity (um/s)'])
        self.stepSizeBox.setValue(self.config['step size (um)'])
        self.moveToXLine.setText(str(self.config['move to X (um)']))
        self.moveToYLine.setText(str(self.config['move to Y (um)']))
        self.posXLine.setText(str(self.config['position X (um)']))
        self.posYLine.setText(str(self.config['position Y (um)']))
        self.intervalLine.setText(str(self.config['update interval (s)']))
        self.backlashXLine.setText(str(self.config['backlash X (um)']))
        self.backlashYLine.setText(str(self.config['backlash Y (um)']))
        self.last_X_direction = self.config['last X direction']
        self.last_Y_direction = self.config['last Y direction']
        self.pixelToDistLine.setText(str(self.config['pixel to distance conversion']))
        self.misalignmentLine.setText(str(self.config['camera - motion stages misalignment angle (degree)']))
        if self.config['invert X']>0:
            self.invertXBox.setChecked(False)
        else:
            self.invertXBox.setChecked(True)
        if self.config['invert Y']>0:
            self.invertYBox.setChecked(False)
        else:
            self.invertYBox.setChecked(True)        

    def initialize_camera_plot_widgets (self):
        # init plot
        self.cameraPlot.showAxis('top', show=False)
        self.cameraPlot.showAxis('right', show=False)
        self.cameraPlot.showAxis('bottom', show=False)
        self.cameraPlot.showAxis('left', show=False)
        # self.cameraPlot.getAxis('top').setStyle(showValues=False)
        # self.cameraPlot.getAxis('right').setStyle(showValues=False)

        # lock aspect ratio
        self.cameraPlot.getViewBox().setAspectLocked(True, ratio=1)         

        self.image = np.random.rand(1000,1000)*25
        self.img_item = pg.ImageItem(self.image)
        self.cameraPlot.addItem(self.img_item)
        # set colormap
        colormap = self.color_map_lookup_table[self.colorMapBox.currentText()]
        colormap = pg.colormap.get(colormap)
        self.img_item.setLookupTable(colormap.getLookupTable(), update=True)
        # initial set of upper and lower bounds of color map
        self.min_intensity = 0
        self.max_intensity = 25
        self.minIntensityBox.setValue(int(self.min_intensity))
        self.maxIntensityBox.setValue(int(self.max_intensity))
        self.img_item.setLevels((self.min_intensity, self.max_intensity))
        
        # draw crosshair indicating laser spot location
        color = self.laserColorBox.currentText()
        size  = int(self.laserSizeBox.value())
        self.laser_indicator = pg.TargetItem(pos=(self.laser_pos_x, self.laser_pos_y), size=size, symbol='x', pen=pg.mkPen(color), brush=pg.mkBrush(color), movable=True)
        self.cameraPlot.addItem(self.laser_indicator)

        # init widgets and attributes
        self.minIntensityBox.valueChanged.connect(self.adjust_color_levels)
        self.maxIntensityBox.valueChanged.connect(self.adjust_color_levels)
        self.colorMapBox.currentIndexChanged.connect(self.change_color_map)
        self.autoscaleButton.clicked.connect(self.autoscale_image)
        self.laserColorBox.currentIndexChanged.connect(self.change_laser_indicator_color)
        self.laserSizeBox.valueChanged.connect(self.change_laser_indicator_size)
        
        self.live_update_bool = False
        self.liveButton.clicked.connect(self.live_button_clicked)
        self.liveButton.setStyleSheet("QPushButton#liveButton {color: rgb(0, 255, 0);background-color:rgb(0, 0, 0);border: 2px solid rgb(0, 255, 0);border-radius: 5px}")

    def initialize_manual_movement_widgets (self):
        # here we are connecting the arrow buttons that move the x and y stages:
        # the idea is that we move one step with the defined step size if the button is clicked (i.e. pressed for a short time),
        # and if the button is pressed for longer we will go into continuous movement that is stopped when the button is released
        # what will happen is that ..._pressed will start a timer
        # if the timer is on for 100 ms it will trigger the "trigger_continuous_movement" fct
        # when the button is released, either the continuous movement is stopped (if the timer has been on for over 100 ms)
        # or the individual step movement will be performed
        self.yUpBtn.pressed.connect(lambda button= "up" : self.arrow_button_pressed(button))
        self.yDownBtn.pressed.connect(lambda button= "down" : self.arrow_button_pressed(button))
        self.xLeftBtn.pressed.connect(lambda button= "left" : self.arrow_button_pressed(button))
        self.xRightBtn.pressed.connect(lambda button= "right" : self.arrow_button_pressed(button))
        self.yUpBtn.released.connect(self.arrow_button_released)
        self.yDownBtn.released.connect(self.arrow_button_released)
        self.xLeftBtn.released.connect(self.arrow_button_released)
        self.xRightBtn.released.connect(self.arrow_button_released)
        # also need a timer for this
        self.hold_timer = QTimer(self)
        self.hold_timer.setSingleShot(True)  # Only trigger once
        self.hold_timer.timeout.connect(self.trigger_continuous_movement)  # Function to run after 100ms
        self.continuous_movement_triggered = False

        # timer to update the fields indicating motor status regularly
        self.motor_states_timer = QTimer(self)
        self.motor_states_timer.timeout.connect(self.read_motor_states)
        self.motor_states_timer.start(250)

        self.homingBtn.clicked.connect(self.home_button_pressed)
        self.stopBtn.clicked.connect(self.stop_all_movement)
        self.moveToBtn.clicked.connect(self.move_to_button_pressed)
        self.readPosBtn.clicked.connect(self.read_pos_pressed)

    def initialize_auto_movement_widgets (self):
        # init reference image plot
        if self.init_ref_image is None:
            im = deepcopy(self.image)
        else:
            im = self.init_ref_image
        self.AlignImages = AlignImages(reference_image=im, image_to_align=im, method='affine partial 2D')
        self.referenceImagePlot.showAxis('top', show=False)
        self.referenceImagePlot.showAxis('right', show=False)
        self.referenceImagePlot.showAxis('bottom', show=False)
        self.referenceImagePlot.showAxis('left', show=False)
        # lock aspect ratio
        self.referenceImagePlot.getViewBox().setAspectLocked(True, ratio=1)         

        self.ref_img_item = pg.ImageItem(self.AlignImages.ref_im)
        self.referenceImagePlot.addItem(self.ref_img_item)

        # init auto movement widgets
        self.referenceButton.clicked.connect(self.update_reference_image)
        self.moveToRefBtn.clicked.connect(self.move_to_reference)
        self.measDistToRefBtn.clicked.connect(self.measure_current_dist_to_ref)
    
    def initialize_zstage_widgets (self):
        self.zUpBtn.clicked.connect(lambda b, direction='up': self.move_z_stage(direction))
        self.zDownBtn.clicked.connect(lambda b, direction='down': self.move_z_stage(direction))
        self.multimeterBtn.clicked.connect(self.monitor_multimeter)

    def monitor_multimeter (self):
        if not self.multimeterDevice is None:
            multimeter_monitor = {'y axis' : {'label' : 'Voltage', 'unit' : 'V'},
                           'monitor item' : self.multimeterDevice.return_last_reading, 'monitor param' : None}
            self.multimeterMon = Monitor(multimeter_monitor, reactor= self.reactor, parent= self)
            self.multimeterMon.show()
            self.multimeterMon.monitor()

    @inlineCallbacks
    def wait_for_z_movement_to_finish(self, c=None, abort_time=10, check_interval=0.1):
        self.sleep(check_interval)
        done_bool = False
        old_pos = yield self.zstageDevice.status["position"]
        start_time = time()
        while not done_bool:
            new_pos = yield self.zstageDevice.status["position"]
            if new_pos == old_pos:
                done_bool = True
                print('done moving')
            if (time()-start_time) > abort_time:
                print(time()-start_time)
                print((time()-start_time) > abort_time)
                done_bool = True
                print (f"The device did not stop moving within {abort_time} seconds")
            old_pos = new_pos
            yield self.sleep(check_interval)

    @inlineCallbacks
    def move_z_stage(self, direction):
        self.zUpBtn.setEnabled(False)
        self.zDownBtn.setEnabled(False)
        self.zStatusLine.setText('Moving')
        try:
            step_size = int(self.encoderSizeBox.value())
            if direction == 'up':
                step_size=-step_size
                # here up is a negative number because of how the motor is mounted
            yield self.zstageDevice.move_relative(step_size)
            yield self.wait_for_z_movement_to_finish()
        except Exception as e:
            print('Error moving z-stage ...')
            print(e)
        self.zUpBtn.setEnabled(True)
        self.zDownBtn.setEnabled(True)
        self.zStatusLine.setText('Idle')
    
    def adjust_color_levels (self):
        self.min_intensity = self.minIntensityBox.value()
        self.max_intensity = self.maxIntensityBox.value()
        self.img_item.setLevels((self.min_intensity, self.max_intensity))

    def autoscale_image (self):
        self.min_intensity = np.min(self.image)  # Set your desired minimum intensity
        self.minIntensityBox.setValue(self.min_intensity)
        self.max_intensity = np.max(self.image)  # Set your desired maximum intensity
        self.maxIntensityBox.setValue(self.max_intensity)
        self.img_item.setLevels((self.min_intensity, self.max_intensity))

    def change_color_map (self):
        # set colormap
        colormap = self.color_map_lookup_table[self.colorMapBox.currentText()]
        colormap = pg.colormap.get(colormap)
        self.img_item.setLookupTable(colormap.getLookupTable(), update=True)

    def update_reference_image (self):
        self.AlignImages.ref_im = deepcopy(self.image)
        self.ref_img_item.setImage(self.AlignImages.ref_im)
        # in the past this camera window has frozen; so I am (pretty arbitrarily) adding this here so that at least
        # a somewhat recent version of the config is saved if that happens;
        # particularly, I added the position of the laser spot into the config so that I can even remotely start
        # the measurement again, even if the camera window has frozen
        self.save_config()

    @inlineCallbacks
    def measure_current_dist_to_ref (self, c=None):
        self.AlignImages.al_im = deepcopy(self.image)
        # translation is in pixels
        translation = yield self.AlignImages.align_images()
        # convert from pixels to microns
        scale = float(self.pixelToDistLine.text())
        translation = translation * scale
        # correct for a small angle mismatch between camera and motion stages
        misalignment_angle = float(self.misalignmentLine.text())*np.pi/180
        rotation_matrix = np.array([[np.cos(misalignment_angle),-np.sin(misalignment_angle)],
                                    [np.sin(misalignment_angle), np.cos(misalignment_angle)]])
        translation = np.dot(rotation_matrix, translation)
        print('x: ', translation[0])
        print('y: ', translation[1])
        distance = np.sqrt(translation[0]**2 + translation[1]**2)
        self.distToRefLine.setText(str(np.round(distance, 3)))
        return -translation

    @inlineCallbacks
    def move_to_reference (self, c=None):
        # get current distance to reference image
        self.image = yield np.array(self.cameraDevice.latest_frame())
        # self.image = yield np.array(self.cameraDevice.grab_image())
        translation = yield self.measure_current_dist_to_ref()
      
        # move in x-direction
        x_step = np.absolute(translation[0])/1e3 # convert to mm
        factor = np.sign(translation[0])
        # manual checkbox to invert the direction of movement;
        # this is because it isn't guaranteed that the camera
        # is perfectly aligned with motor directions
        if self.invertXBox.isChecked():
            factor = -factor
        # compensate for backlash if the direction of the movement has changed
        if factor != self.last_X_direction:
            self.last_X_direction = deepcopy(factor)
            x_step = x_step + float(self.backlashXLine.text())/1e3
        yield self.xStageDevice.step_size(factor*x_step)
        step_size = yield self.xStageDevice.step_size()
        print('x step size changed to: ',step_size)
        yield self.xStageDevice.move_relative()
        
        # move in y-direction
        y_step = np.absolute(translation[1])/1e3
        factor = np.sign(translation[1])
        # manual checkbox to invert the direction of movement;
        # this is because it isn't guaranteed that the camera
        # is perfectly aligned with motor directions
        if self.invertYBox.isChecked():
            factor = -factor
        # compensate for backlash if the direction of the movement has changed
        if factor != self.last_Y_direction:
            self.last_Y_direction = deepcopy(factor)
            y_step = y_step + float(self.backlashYLine.text())/1e3
        yield self.yStageDevice.step_size(factor*y_step)
        step_size = yield self.yStageDevice.step_size()
        print('y step size changed to: ',step_size)
        yield self.yStageDevice.move_relative()

        # wait until movement is over
        busy_bool_x = yield self.xStageDevice.is_device_busy()
        busy_bool_y = yield self.yStageDevice.is_device_busy()
        while busy_bool_x or busy_bool_y:
            yield self.sleep(0.5)
            busy_bool_x = yield self.xStageDevice.is_device_busy()
            busy_bool_y = yield self.yStageDevice.is_device_busy()
        
        yield self.sleep(0.5)
        # measure new distance to reference image
        new_distance = yield self.measure_current_dist_to_ref()
        return new_distance


    def change_laser_indicator_color (self):
        color = self.laserColorBox.currentText()
        self.laser_indicator.setPen(pg.mkPen(color))
        self.laser_indicator.setBrush(pg.mkBrush(color))

    def change_laser_indicator_size (self):
        pos = self.laser_indicator.pos()
        self.cameraPlot.removeItem(self.laser_indicator)
        color = self.laserColorBox.currentText()
        size  = int(self.laserSizeBox.value())
        self.laser_indicator = pg.TargetItem(pos=pos, size=size, symbol='x', pen=pg.mkPen(color), brush=pg.mkBrush(color), movable=True)
        self.cameraPlot.addItem(self.laser_indicator)

    @inlineCallbacks
    def live_update (self, c=None):
        yield self.cameraDevice.start_live_video()
        while self.live_update_bool:
            # Blocks and returns True once the next frame is ready
            # frame_done = yield self.cameraDevice.wait_for_frame()
            frame_done = True
            if frame_done:
                self.image = yield np.array(self.cameraDevice.latest_frame())
                # self.image = yield np.array(self.cameraDevice.grab_image())
                self.img_item.setImage(self.image)
                self.img_item.setLevels((self.min_intensity, self.max_intensity))
                yield self.sleep(float(self.intervalLine.text()))
        yield self.cameraDevice.stop_live_video()
    
    @inlineCallbacks
    def live_button_clicked (self, c=None):
        if self.live_update_bool==True:
            try:
                self.live_update_bool = False
                self.liveButton.setStyleSheet("QPushButton#liveButton {color: rgb(0, 255, 0);background-color:rgb(0, 0, 0);border: 2px solid rgb(0, 255, 0);border-radius: 5px}")
                self.liveButton.setText('Start Live')
            except Exception as e:
                print('Error stopping live capture ...')
                print(e)
        else:
            try:
                self.live_update_bool = True
                self.liveButton.setStyleSheet("QPushButton#liveButton {color: rgb(255, 0, 0);background-color:rgb(0, 0, 0);border: 2px solid rgb(255, 0, 0);border-radius: 5px}")
                self.liveButton.setText('Stop Live')
                yield self.live_update()
            except Exception as e:
                self.liveButton.setStyleSheet("QPushButton#liveButton {color: rgb(0, 255, 0);background-color:rgb(0, 0, 0);border: 2px solid rgb(0, 255, 0);border-radius: 5px}")
                self.liveButton.setText('Start Live')
                self.live_update_bool = False

                print('Error starting live capture ...')
                print(e)

    @inlineCallbacks
    def read_motor_states (self, c=None):
        try:
            if not ((self.xStageDevice is None) or (self.yStageDevice is None)):
                xstate = yield self.xStageDevice.current_motor_state()
                ystate = yield self.yStageDevice.current_motor_state()
                self.stateXLine.setText(xstate)
                self.stateYLine.setText(ystate)
        except Exception as e:
            print('Error reading motor states ...')
            print(e)
    
    @inlineCallbacks
    def while_stage_devices_busy (self, update=0.1):
        """
        checks if x or y stages are busy and disables certain buttons/fields while they are;
        checks every "update" seconds
        """
        try:
            busy_bool_x = yield self.xStageDevice.is_device_busy()
            busy_bool_y = yield self.yStageDevice.is_device_busy()
            # print('x busy? ', busy_bool_x)
            # print('y busy? ', busy_bool_y)

            while busy_bool_x or busy_bool_y:
                yield self.sleep(update)
                self.xLeftBtn.setEnabled(False)
                self.xRightBtn.setEnabled(False)
                self.yUpBtn.setEnabled(False)
                self.yDownBtn.setEnabled(False)
                self.homingBtn.setEnabled(False)
                self.moveToBtn.setEnabled(False)

                busy_bool_x = yield self.xStageDevice.is_device_busy()
                busy_bool_y = yield self.yStageDevice.is_device_busy()

            self.xLeftBtn.setEnabled(True)
            self.xRightBtn.setEnabled(True)
            self.yUpBtn.setEnabled(True)
            self.yDownBtn.setEnabled(True)
            self.homingBtn.setEnabled(True)
            self.moveToBtn.setEnabled(True)
        
        except Exception as e:
            print("could not execute 'while_stages_are_busy' method ...")
            print(e)

    @inlineCallbacks
    def update_motion_control_params (self, direction='right'):
        try:
            new_step_size    = float(self.stepSizeBox.value())/1e3
            new_acceleration = float(self.accelerationBox.value())/1e3
            new_max_vel      = float(self.velocityBox.value())/1e3

            if direction=='up' or direction=='right':
                factor=1
            else:
                factor = -1
            if direction=='left' or direction=='right':
                stageDevice = self.xStageDevice
                # manual checkbox to invert the direction of movement;
                # this is because it isn't guaranteed that the camera
                # is perfectly aligned with motor directions
                if self.invertXBox.isChecked():
                    factor = -factor
                # compensate for backlash if the direction of the movement has changed
                if factor != self.last_X_direction:
                    self.last_X_direction = deepcopy(factor)
                    new_step_size = new_step_size + float(self.backlashXLine.text())/1e3
            else:
                stageDevice = self.yStageDevice
                if self.invertYBox.isChecked():
                    factor = -factor
                if factor != self.last_Y_direction:
                    self.last_Y_direction = deepcopy(factor)
                    new_step_size = new_step_size + float(self.backlashYLine.text())/1e3

            step_size = yield stageDevice.step_size()
            max_velocity, acceleration = yield stageDevice.velocity_params()
            print('current params: step size: ', step_size, '; vel: ', max_velocity, '; acc: ', acceleration)
            # update stage parameters if they are different from current ones
            if step_size != factor*new_step_size:
                yield stageDevice.step_size(factor*new_step_size)
                step_size = yield stageDevice.step_size()
                print('step size changed to: ',step_size)
            if (acceleration != new_acceleration) or (max_velocity != new_max_vel):
                yield stageDevice.velocity_params(new_max_vel, new_acceleration)
                vel, acc = yield stageDevice.velocity_params()
                print('velocity params changed to: vel: ', vel, '; acc: ', acc)
        except Exception as e:
            print('Error updating motion control parameters ...')
            print(e)
            
    # @inlineCallbacks
    # def arrow_button_clicked (self, c, button):
    #     if button=='up' or button=='down':
    #         yield self.update_motion_control_params(button)
    #         yield self.yStageDevice.move_relative()     

    #     elif button=='right' or button=='left':
    #         yield self.update_motion_control_params(button)
    #         yield self.xStageDevice.move_relative()  
        
    #     yield self.while_stage_devices_busy()
    
    def arrow_button_pressed (self, button):
        self.continuous_movement_triggered = False
        self.hold_timer.start(180)
        self.arrow_direction = button

    @inlineCallbacks
    def trigger_continuous_movement (self, c=None):
        try:
            self.continuous_movement_triggered = True
            print('continuous movement triggered')
            if self.invertXBox.isChecked():
                factorx = -1
            else:
                factorx = 1
            if self.invertYBox.isChecked():
                factory = -1
            else:
                factory = 1
            if self.arrow_direction=='up':
                yield self.update_motion_control_params('up')
                yield self.yStageDevice.start_moving(factory)
            elif self.arrow_direction=='down':
                yield self.update_motion_control_params('down')
                yield self.yStageDevice.start_moving(-factory)
            elif self.arrow_direction=='right':
                yield self.update_motion_control_params('right')
                yield self.xStageDevice.start_moving(factorx)
            elif self.arrow_direction=='left':
                yield self.update_motion_control_params('left')
                yield self.xStageDevice.start_moving(-factorx)
            yield self.while_stage_devices_busy()
        except Exception as e:
            print('Error triggering continuous movement ...')
            print(e)


    @inlineCallbacks
    def arrow_button_released (self, c=None):
        if self.continuous_movement_triggered:
            print('stopping continuous movement')
            try:
                # this is the case where the arrow button was pressed for longer than 100 ms
                # the stage should be continuously moving currently
                # here we are stopping the movement upon releasing the button
                if self.arrow_direction=='up' or self.arrow_direction=='down':
                    yield self.yStageDevice.stop_moving(immediate=False)
                elif self.arrow_direction=='right' or self.arrow_direction=='left':
                    yield self.xStageDevice.stop_moving(immediate=False)
                self.continuous_movement_triggered = False
            except Exception as e:
                print('Error stopping continuous movement ...')
                print(e)

        else:
            print('button not pressed long enough for continous movement')
            print('move by step instead')
            # this is the case where the arrow button was pressed for less than 100 ms
            # this is what we consider a "click"
            # the motion stages only move by a step, defined by "step_size"
            self.hold_timer.stop()
            try:
                if self.arrow_direction=='up' or self.arrow_direction=='down':
                    yield self.update_motion_control_params(self.arrow_direction)
                    yield self.yStageDevice.move_relative()
                elif self.arrow_direction=='right' or self.arrow_direction=='left':
                    yield self.update_motion_control_params(self.arrow_direction)
                    yield self.xStageDevice.move_relative()

                yield self.while_stage_devices_busy()
            except Exception as e:
                print('Error moving by step size ...')
                print(e)
        

    @inlineCallbacks
    def home_button_pressed (self, c=None):
        try:
            yield self.xStageDevice.home()
            yield self.yStageDevice.home()    
            # yield self.while_stage_devices_busy()
        except Exception as e:
            print('Error homing ...')
            print(e)

    @inlineCallbacks
    def move_to_button_pressed (self, c=None):
        try:
            yield self.update_motion_control_params('right')
            yield self.update_motion_control_params('up')
            yield self.xStageDevice.move_to_position(float(self.moveToXLine.text())/1e3)
            yield self.yStageDevice.move_to_position(float(self.moveToYLine.text())/1e3)    
            # yield self.while_stage_devices_busy()
        except Exception as e:
            print('Error moving to position ...')
            print(e)

    @inlineCallbacks
    def read_pos_pressed (self, c=None):
        try:
            xpos = yield self.xStageDevice.get_current_position()
            ypos = yield self.yStageDevice.get_current_position()    
            self.posXLine.setText(str(np.round(xpos*1e3,2)))
            self.posYLine.setText(str(np.round(ypos*1e3,2)))
        except Exception as e:
            print('Error reading stepper motor position ...')
            print(e)
    
    @inlineCallbacks
    def stop_all_movement (self, c=None):
        yield self.xStageDevice.stop_moving()
        yield self.yStageDevice.stop_moving()
    
    def save_config (self):
        laser_pos_x, laser_pos_y = self.laser_indicator.pos()   
        self.config['laser spot location x (pixel)'] = int(laser_pos_x)
        self.config['laser spot location y (pixel)'] = int(laser_pos_y)     
        self.config['acceleration (um/s^2)'] = self.accelerationBox.value()
        self.config['velocity (um/s)']       = self.velocityBox.value()
        self.config['step size (um)']        = self.stepSizeBox.value()
        self.config['move to X (um)']        = self.moveToXLine.text()
        self.config['move to Y (um)']        = self.moveToYLine.text()
        self.config['position X (um)']       = self.posXLine.text()
        self.config['position Y (um)']       = self.posYLine.text()
        self.config['update interval (s)']   = self.intervalLine.text()
        self.config['backlash X (um)']       = self.backlashXLine.text()
        self.config['backlash Y (um)']       = self.backlashYLine.text()
        self.config['last X direction']      = self.last_X_direction
        self.config['last Y direction']      = self.last_Y_direction
        self.config['pixel to distance conversion'] = self.pixelToDistLine.text()
        self.config['camera - motion stages misalignment angle (degree)'] = self.misalignmentLine.text()
        if self.invertXBox.isChecked():
            self.config['invert X'] = -1
        else:
            self.config['invert X'] = 1
        if self.invertYBox.isChecked():
            self.config['invert Y'] = -1
        else:
            self.config['invert Y'] = 1

        with open(self.config_path, "w") as outfile:
            json.dump(self.config, outfile, indent=4)

        np.save(self.reference_image_path, self.AlignImages.ref_im)

    #async sleep function - GUI is operable while function sleeps
    def sleep(self, secs):
        d = Deferred()
        self.reactor.callLater(secs,d.callback,'Sleeping')
        return d

    def on_close_event(self, event):
        # Run your function when the window is closed
        self.save_config()
        self.motor_states_timer.stop()

        # Call the default closeEvent to close the window
        super().closeEvent(event)  



if __name__ == '__main__':
    cam = uc480.UC480_Camera(reopen_policy='new')
    cam.open()

    QApplication.setStyle('Fusion')
    app = QApplication([])
    app.setStyle('Windows')
    import qt5reactor
    qt5reactor.install()
    from twisted.internet import reactor
    win = Camera(camera=cam, reactor=reactor, operating_system='windows')
    win.show()
    app.exec()

    