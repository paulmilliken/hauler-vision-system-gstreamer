#!/usr/bin/python

'''This program displays an RTSP video stream from an Axis camera.  More than
one camera is allowed and user can switch between camera views.  Currently,
the user can also digitally zoom, pan and tilt and digitally lighten and darken
the image.

To do:
  * Use optical lightening and darkening via cgi interface instead of digitally

This code was developed at Scion as part of FFR's hauler-vision project to
allow hauler operators to view live video from cameras in the cutover and on
the tailhold.  It will also be used as part of a tele-operation system for an
felling/bunching excavator.

The Axis P1347 camera appears to be capable of streaming H.264 encoded video up
to resolutions of 2560x1920.  However, a resolution of 1600x1200 is the highest
that I got to work with mjpeg encoding.  The latency of H.264 encoding is too
high for our application so we'll run with mjpeg at a lower resolution.  This
means we can't digitally zoom as much as I would have liked.

The network topology is:
         _____________         ______________
        | computer    |       | wireless A/P |-------------.
        | 192.168.1.3 |-------| 192.168.1.53 |------------.|
        |_____________|       |______________|-----------.||
                                                         |||
         _____________         __________________        |||
        | hauler cam  |       | wireless station |       |||
        | 192.168.1.61|-------| 192.168.1.56     |-------'||
        |_____________|       |__________________|        ||
                                                          ||
         _____________         __________________         ||
        | tail cam    |       | wireless station |        ||
        | 192.168.1.60|-------| 192.168.1.54     |--------'|
        |_____________|       |__________________|         |
                                                           |
         _____________         __________________          |
        | cutover cam |       | wireless station |         |
        | 192.168.1.62|-------| 192.168.1.92     |---------'
        |_____________|       |__________________|       

  * Computer's IP address is 192.168.1.3; access point is 192.168.1.53
  * Tailhold camera is 192.168.1.60; wireless station is 192.168.1.54?
  * Hauler camera is 192.168.1.61; wireless station is 192.168.1.56
  * Tripod camera is 192.168.1.62; wireless station is 192.168.1.92
All wireless devices are bridged.'''

__author__ = 'Paul Milliken'
__licence__ = 'GPLv3'
__version__ = 0.1
__maintainer__ = 'Paul Milliken'
__email__ = 'paul.milliken@gmail.com'
__status__ = 'Prototype'

import subprocess
import AxisRtsp
import pygtk
import gtk
import time
import gobject
gobject.threads_init()

class OperatorInterface:
    '''An instatiation of the OperatorInterface class gives a fullscreen view
    of the RTSP video stream at the IP address given by the argument.  The user
    can swap cameras and digitally pan, tilt and zoom.  Currently, only Axis 
    P1347 cameras have been tested.'''

    def __init__(self, ipAddressList, pipelineType='lightenOnly'):
        '''Sets up the GTK interface and the RTSP pipelines using GStreamer'''
        self.ipAddressList = ipAddressList
        self.pipelineType = pipelineType
        self.numberOfCameras = len(ipAddressList)
        self.initialiseVariables()
        self.setUpGTKWindow()
        self.setUpGTKCallbacks()
        self.instantiateRtspPipeline()

    def initialiseVariables(self):
        '''Sets default values of certain variables'''
        self.windowIsFullscreen = False
        self.currentCamera = 0
        # variables relating to zooming, panning and tilting:
        self.deltaLeftRight = 4 # number of pixels per increment
        self.deltaTopBottom = 3
        # variables relating to image brightness:
        self.brightness = [0] * self.numberOfCameras
        self.deltaBrightness = 0.010
        # variables for digital zoom, pan, tilt:
        self.left = [0] * self.numberOfCameras #left border (pixels)
        self.right = [0] * self.numberOfCameras #left border (pixels)
        self.top = [0] * self.numberOfCameras #left border (pixels)
        self.bottom = [0] * self.numberOfCameras #left border (pixels)

    def setUpGTKWindow(self):
        '''There is only one fullscreen window with no buttons'''
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.vbox = gtk.VBox()
        self.drawingArea = gtk.DrawingArea()
        self.vbox.pack_start(self.drawingArea)
        self.window.add(self.vbox)
        self.window.show_all()
        self.goFullscreen()
    
    def setUpGTKCallbacks(self):
        self.window.connect('destroy', self.quitApplication)
        self.window.connect('key-press-event', self.onKeypress)
    
    def quitApplication(self, widget):
        gtk.main_quit()
        #subprocess.call(['/sbin/shutdown','-h','now'])

    def onKeypress(self, widget, event):
        '''The system is designed to be used with a Manhattan numberpad.  The
        numlock can be on or off.  GTK references the keys on the keypad by 
        gtk.keysyms.KP_*.  There is also an option to use the keyboard
        in case the numberpad is not available'''
        # print(event.keyval)  # Uncomment this line to determine keyvals
        if (event.keyval==gtk.keysyms.BackSpace or \
            event.keyval==gtk.keysyms.q):
            self.quitApplication(widget)
        if (event.keyval==gtk.keysyms.KP_5 or \
            event.keyval==gtk.keysyms.KP_Begin or \
            event.keyval==gtk.keysyms.p):
            self.rtspPipeline.pauseOrUnpauseVideo()
        if (event.keyval==gtk.keysyms.KP_Enter or \
            event.keyval==gtk.keysyms.space):
            self.incrementCamera()
        if (event.keyval==gtk.keysyms.KP_Decimal or \
            event.keyval==gtk.keysyms.KP_Delete or \
            event.keyval==gtk.keysyms.f):
            self.toggleFullscreen()
        if (event.keyval==gtk.keysyms.KP_Add or \
            event.keyval==gtk.keysyms.equal):
            self.zoomIn()
        if (event.keyval==gtk.keysyms.KP_Subtract or \
            event.keyval==gtk.keysyms.minus):
            self.zoomOut()
        if (event.keyval==gtk.keysyms.KP_Up or event.keyval==gtk.keysyms.KP_8 \
            or event.keyval==gtk.keysyms.Up):
            self.goUp()
        if (event.keyval==gtk.keysyms.KP_Down or \
            event.keyval==gtk.keysyms.Down or event.keyval==gtk.keysyms.KP_2):
            self.goDown()
        if (event.keyval==gtk.keysyms.KP_Left or \
            event.keyval==gtk.keysyms.KP_4 or event.keyval==gtk.keysyms.Left):
            self.goLeft()
        if (event.keyval==gtk.keysyms.KP_Right or \
            event.keyval==gtk.keysyms.KP_6 or event.keyval==gtk.keysyms.Right):
            self.goRight()
        if (event.keyval==gtk.keysyms.KP_Divide or \
            event.keyval==gtk.keysyms.l):
            self.brighten()
        if (event.keyval==gtk.keysyms.KP_Multiply or \
            event.keyval==gtk.keysyms.d):
            self.darken()
  
    def incrementCamera(self):
        '''changes to the next camera in the rtspPipelineList and reinstates
        crop and brightness parameters'''
        self.incrementCurrentCameraVariable()
        self.rtspPipeline.setPipelineStateToNull()
#        self.updateRtspPipelineParameters()
        self.rtspPipeline.setPipelineStateToPlaying()
    
    def incrementCurrentCameraVariable(self):
        '''self.currentCamera is used to identify the correct element in 
        self.ipAddressList which is a list of camera ip addresses'''
        tmp = self.currentCamera + 1
        if tmp<self.numberOfCameras:
            self.currentCamera = tmp
        else:
            self.currentCamera = 0
        print('currentCamera = %d' % self.currentCamera)

    def updateRtspPipelineParameters(self):
        '''updates IP address and reinstates crop and brightness parameters'''
        self.rtspPipeline.resetIPAddress(self.ipAddressList[self.currentCamera])
        self.rtspPipeline.setCurrentCropProperties(\
            self.left[self.currentCamera], self.right[self.currentCamera],\
            self.top[self.currentCamera], self.bottom[self.currentCamera])
        try:
            self.rtspPipeline.videobalance.set_property('brightness', \
                self.brightness[self.currentCamera])
        except:
            print('Cannot set brightness.  Maybe no videobalance element')
        if self.pipelineType=='toFile':
            self.rtspPipeline.assignOutputFilename()

    def toggleFullscreen(self):
        if (self.windowIsFullscreen==True):
            self.goUnfullscreen()
        else:
            self.goFullscreen()

    def goFullscreen(self):
        '''sets the window to fullscreen mode'''
        self.window.fullscreen()
        self.windowIsFullscreen = True

    def goUnfullscreen(self):
        '''sets the window to unfullscreen mode'''
        self.window.unfullscreen()
        self.windowIsFullscreen = False

    def zoomIn(self):
        '''Digitally zoom in by adjusting border sizes in crop element'''
        # set maximum border size assuming 1600x1200 image:
        maxLeftPlusRight = 1200
        if (self.left[self.currentCamera]+self.right[self.currentCamera]) < \
            (maxLeftPlusRight + 2*self.deltaLeftRight):
            self.left[self.currentCamera] = self.left[self.currentCamera] + \
                self.deltaLeftRight
            self.right[self.currentCamera] = self.right[self.currentCamera] + \
                self.deltaLeftRight
            self.top[self.currentCamera] = self.top[self.currentCamera] + \
                self.deltaTopBottom
            self.bottom[self.currentCamera] = self.bottom[self.currentCamera] +\
                self.deltaTopBottom
            self.rtspPipeline.setCurrentCropProperties(\
                self.left[self.currentCamera], self.right[self.currentCamera],\
                self.top[self.currentCamera], self.bottom[self.currentCamera])

    def zoomOut(self):
        '''Digitally zoom out by reducing border sizes in crop element'''
        # get border sizes of cropped area:
        self.centraliseImageIfRequired()
        # Now adjust borders:
        if ((self.left[self.currentCamera]+self.right[self.currentCamera]) > \
            2*self.deltaLeftRight):
            self.right[self.currentCamera] = self.right[self.currentCamera] - \
                self.deltaLeftRight
            self.left[self.currentCamera] = self.left[self.currentCamera] - \
                self.deltaLeftRight
            self.top[self.currentCamera] = self.top[self.currentCamera] - \
                self.deltaTopBottom
            self.bottom[self.currentCamera] = self.bottom[self.currentCamera] \
                - self.deltaTopBottom
            self.rtspPipeline.setCurrentCropProperties(\
                self.left[self.currentCamera], \
                self.right[self.currentCamera], \
                self.top[self.currentCamera], \
                self.bottom[self.currentCamera])

    def centraliseImageIfRequired(self):
        '''centralise cropped image slightly if unzooming would result in a
        negative border on any side of the cropped area'''
        if self.left[self.currentCamera]<self.deltaLeftRight:
            self.goRight()
        if self.right[self.currentCamera]<self.deltaLeftRight:
            self.goLeft()
        if self.top[self.currentCamera]<self.deltaTopBottom:
            self.goDown()
        if self.bottom[self.currentCamera]<self.deltaTopBottom:
            self.goUp()

    def goUp(self):
        '''Digitally pan up by adjusting borders in crop element'''
        if self.top[self.currentCamera]>=self.deltaTopBottom:
            self.top[self.currentCamera] = self.top[self.currentCamera] - \
                self.deltaTopBottom
            self.bottom[self.currentCamera] = self.bottom[self.currentCamera] \
                + self.deltaTopBottom
            self.rtspPipeline.setCurrentCropProperties(\
                self.left[self.currentCamera], self.right[self.currentCamera],\
                self.top[self.currentCamera], self.bottom[self.currentCamera])
            
    def goDown(self):
        '''Digitally pan down by adjusting borders in crop element'''
        if self.bottom[self.currentCamera]>=self.deltaTopBottom:
            self.top[self.currentCamera] = self.top[self.currentCamera] + \
                self.deltaTopBottom
            self.bottom[self.currentCamera] = self.bottom[self.currentCamera] \
                - self.deltaTopBottom
            self.rtspPipeline.setCurrentCropProperties(\
                self.left[self.currentCamera], self.right[self.currentCamera],\
                self.top[self.currentCamera], self.bottom[self.currentCamera])
            
    def goLeft(self):
        '''Digitally pan left'''
        if self.left[self.currentCamera]>=self.deltaLeftRight:
            self.left[self.currentCamera] = self.left[self.currentCamera] - \
                self.deltaLeftRight
            self.right[self.currentCamera] = self.right[self.currentCamera] + \
                self.deltaLeftRight
            self.rtspPipeline.setCurrentCropProperties\
                (self.left[self.currentCamera], \
                self.right[self.currentCamera], self.top[self.currentCamera], \
                self.bottom[self.currentCamera])
        
    def goRight(self):
        '''Digitally pan right'''
        if self.right[self.currentCamera]>=self.deltaLeftRight:
            self.left[self.currentCamera] = self.left[self.currentCamera] + \
                self.deltaLeftRight
            self.right[self.currentCamera] = self.right[self.currentCamera] - \
                self.deltaLeftRight
            self.rtspPipeline.setCurrentCropProperties\
                (self.left[self.currentCamera], \
                self.right[self.currentCamera], self.top[self.currentCamera], \
                self.bottom[self.currentCamera])

    def brighten(self):
        '''Digitally brighten image'''
        maxBrightness = 1.0
        if (self.brightness[self.currentCamera]<(maxBrightness - \
            self.deltaBrightness)):
            self.brightness[self.currentCamera] = \
                self.brightness[self.currentCamera] + self.deltaBrightness
            try:
                self.rtspPipeline.videobalance.set_property('brightness', \
                    self.brightness[self.currentCamera])
            except:
                print('Cannot set brightness.  Maybe no videobalance element')

    def darken(self):
        '''Digitally unbrighten image'''
        minBrightness = -1.0
        if (self.brightness[self.currentCamera]>(minBrightness + \
            self.deltaBrightness)):
            self.brightness[self.currentCamera] = \
                self.brightness[self.currentCamera] - self.deltaBrightness
            try:
                self.rtspPipeline.videobalance.set_property('brightness', \
                    self.brightness[self.currentCamera])
            except:
                print('Cannot set brightness.  Maybe no videobalance element')

    def instantiateRtspPipeline(self):
        '''Danger'''
        if self.pipelineType=='simple':
            self.rtspPipeline = AxisRtsp.RtspPipelineSimple(\
                self.ipAddressList[self.currentCamera], \
                self.drawingArea.window.xid)
        elif self.pipelineType=='lightenOnly':
            self.rtspPipeline = AxisRtsp.RtspPipelineLightenOnly(
                self.ipAddressList[self.currentCamera], \
                self.drawingArea.window.xid)
        elif self.pipelineType=='toFileAndDisplay':
            self.rtspPipeline = AxisRtsp.RtspPipelineToFileAndDisplay(\
                self.ipAddressList[self.currentCamera], \
                self.drawingArea.window.xid)
        elif self.pipelineType=='lightenPTZ':
            self.rtspPipeline = AxisRtsp.RtspPipelineToDisplay(\
                self.ipAddressList[self.currentCamera], \
                self.drawingArea.window.xid)
        else:
            print('Unknown argument self.pipelineType=%s' % self.pipelineType)
            print('Using simple pipeline instead')
            AxisRtsp.RtspPipelineSimple(self.ipAddressList[self.currentCamera],\
                self.drawingArea.window.xid)

def test1():
    '''One camera and no PTZ or brightening available'''
    operatorInterface = OperatorInterface(['192.168.1.62'], \
        pipelineType='simple')
    operatorInterface.rtspPipeline.setPipelineStateToPlaying()
    gtk.main()
    
def test2():
    '''One camera lighten function available'''
    operatorInterface = OperatorInterface(['192.168.1.62'], \
        pipelineType='lightenOnly')
    operatorInterface.rtspPipeline.setPipelineStateToPlaying()
    gtk.main()
    
def test3():
    '''One camera lighten, record to file and PTZ available'''
    operatorInterface = OperatorInterface(['192.168.1.62'], \
        pipelineType='toFileAndDisplay')
    operatorInterface.rtspPipeline.setPipelineStateToPlaying()
    gtk.main()
    
def test4():
    '''One camera lighten and PTZ available'''
    operatorInterface = OperatorInterface(['192.168.1.62'], \
        pipelineType='lightenPTZ')
    operatorInterface.rtspPipeline.setPipelineStateToPlaying()
    gtk.main()
    
if __name__=='__main__':
    testInterface = test4()

