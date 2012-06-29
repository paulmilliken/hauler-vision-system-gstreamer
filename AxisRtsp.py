#!/usr/bin/python

'''This module contains the lower-level classes that allow an RTSP pipeline to
be built and manipulated.  Currently, only Axis P1347 cameras have been tested
with motion jpeg encoding.'''

__author__ = 'Paul Milliken'
__licence__ = 'GPLv3'
__version__ = 0.1
__maintainer__ = 'Paul Milliken'
__email__ = 'paul.milliken@gmail.com'
__status__ = 'Prototype'

import pygst
pygst.require('0.10')
import gst
import gtk
import datetime

class RtspBaseClass:
    '''RtspBaseClass is a base class that provides the building blocks for other
    classes that create rtsp pipelines.  Commonly used gstreamer pipeline 
    elements and callback methods are defined within.'''
    
    def createEmptyPipeline(self):
        self.pipeline = gst.Pipeline('mypipeline')

    def createVideobalanceElement(self):
        self.videobalance = gst.element_factory_make('videobalance', \
            'videobalance')
        self.videobalance.set_property('brightness', 0.0)

    def createVideoscaleElement(self):
        self.videoscale = gst.element_factory_make('videoscale', 'videoscale')

    def createVideorateElement(self):
        self.videorate = gst.element_factory_make('videorate', 'videorate')

    def createCapsfilterElement(self):
        self.capsfilter = gst.element_factory_make('capsfilter', 'capsfilter')
        caps = 'video/x-raw-yuv,framerate=10/1,width=1024,height=768'
        self.capsfilter.set_property('caps',gst.caps_from_string(caps))

    def createFfmpegcolorspaceElement(self):
        self.ffmpegcolorspace = gst.element_factory_make('ffmpegcolorspace', \
            'ffmpegcolorspace')

    def createTeeElement(self):
        self.tee = gst.element_factory_make('tee', 'tee')

    def createQueueFileElement(self):
        self.queueFile = gst.element_factory_make('queue', 'queueFile')

    def createQueueDisplayElement(self):
        self.queueDisplay = gst.element_factory_make('queue', 'queueDisplay')

    def createTheoraencElement(self):
        self.theoraenc = gst.element_factory_make('theoraenc', 'theoraenc')

    def createJpegencElement(self):
        self.jpegenc = gst.element_factory_make('jpegenc', 'jpegenc')

    def createOggmuxElement(self):
        self.oggmux = gst.element_factory_make('oggmux', 'oggmux')

    def createAvimuxElement(self):
        self.avimux = gst.element_factory_make('avimux', 'avimux')

    def createFilesinkElement(self):
        self.filesink = gst.element_factory_make('filesink', 'filesink')
        self.assignOutputFilename()

    def assignOutputFilename(self):
        '''self.outputFilename is of the form 
        year_month_day_hour_minute_second.avi'''
        now = datetime.datetime.now()
        outputFilename = \
            './%s_%s_%s_%s_%s_%s.avi' % (now.year, \
            str(now.month).zfill(2), str(now.day).zfill(2), \
            str(now.hour).zfill(2), str(now.minute).zfill(2), \
            str(now.second).zfill(2))
        self.filesink.set_property('location', outputFilename)

    def createRtspsrcElement(self):
        '''The name of each rtsp source element is a string representing its
        ipaddress'''
        self.source = gst.element_factory_make('rtspsrc', 'source')
        self.source.set_property('latency', 0)
        self.formRtspUri()
        self.source.set_property('location', self.rtspUri)

    def resetIPAddress(self, ipAddress):
        self.ipAddress = ipAddress
        self.formRtspUri()
        print('Attempting to change uri to %s' % self.rtspUri)
        self.source.set_property('location', self.rtspUri)
        print(self.source.get_property('location'))

    def formRtspUri(self):
        '''The rtsp stream can be accessed via this string on Axis cameras:'''
        self.rtspUri = \
            'rtsp://%s:554/axis-media/media.amp?videocodec=jpeg&audio=0' %\
            (self.ipAddress)

    def createDepayElement(self):
        '''creates jpeg depayer element'''
        self.depay = gst.element_factory_make('rtpjpegdepay','mydepay')
        
    def createDecodeElement(self):
        '''creates mjpeg decoder element'''
        self.decode = gst.element_factory_make('ffdec_mjpeg','mydecode')

    def createCropElement(self):
        self.crop = gst.element_factory_make('videocrop','mycropper')
        self.crop.set_property('top', 0)
        self.crop.set_property('bottom', 0)
        self.crop.set_property('left', 0)
        self.crop.set_property('right', 0)
        
    def createXvimagesinkElement(self):
        '''Use an xvimagesink rather than ximagesink to utilise video chip
        for scaling etc.'''
        self.xvimagesink = gst.element_factory_make('xvimagesink', \
            'xvimagesink')
        self.xvimagesink.set_xwindow_id(self.xid)
    
    def createPipelineCallbacks(self):
        '''Note that source is an rtspsrc element which has a dynamically 
        created source pad.  This means it can only be linked after the pad has
        been created.  Therefore, the linking is done with the callback function
        onPadAddedToRtspsrc(...):'''
        self.source.connect('pad-added', self.onPadAddedToRtspsrc)
        self.source.connect('pad-removed', self.onPadRemovedFromRtspsrc)

    def onPadAddedToRtspsrc(self, rtspsrc, pad):
        '''This callback is required because rtspsrc elements have
        dynamically created pads.  So linking can only occur after a pad
        has been created.  Furthermore, only the rtspsrc for the currently
        selected camera is linked to the depayer.'''
        print('pad added to rtspsrc element.')
        self.xvimagesink.set_xwindow_id(self.xid)
        depaySinkPad = self.depay.get_pad('sink')
        pad.link(depaySinkPad)

    def onPadRemovedFromRtspsrc(self, rtspsrc, pad):
        '''Unlinks the rtspsrc element from the depayer'''
        print('pad removed from rtspsrc element.')
        depaySinkPad = self.depay.get_pad('sink')
        pad.unlink(depaySinkPad)

    def pauseOrUnpauseVideo(self):
        '''Toggles between the paused and playing states'''
        if (self.pipeline.get_state()[1]==gst.STATE_PAUSED):
            self.setPipelineStateToPlaying()
        else:
            self.setPipelineStateToPaused()
    
    def setPipelineStateToPlaying(self):
        self.pipeline.set_state(gst.STATE_PLAYING)

    def setPipelineStateToPaused(self):
        self.pipeline.set_state(gst.STATE_PAUSED)

    def setPipelineStateToNull(self):
        self.pipeline.set_state(gst.STATE_NULL)

    def setCurrentCropProperties(self, left, right, top, bottom):
        '''Sets borders for the videocrop element'''
        try:
            self.crop.set_property('left', left)
            self.crop.set_property('right', right)
            self.crop.set_property('top', top)
            self.crop.set_property('bottom', bottom)
        except:
            print('Cannot set crop properties.  Check videocrop element exists')
 
class RtspPipelineToDisplay(RtspBaseClass):
    '''This class creates and rtsp pipeline that takes displays an rtsp stream
    to an xvimagesink that is displayed in a GTK window.  Arguments are the ip
    address of the camera and the xwindow id where the image will be displayed.
    The Gstreamer pipeline elements are inherited from the RtspBaseClass 
    class.'''
    
    def __init__(self, ipAddress, xid):
        self.ipAddress = ipAddress
        # xid is the xwindow I.D. where the video stream will be displayed:
        self.xid = xid
        self.createGstreamerPipeline()
        
    def createGstreamerPipeline(self):
        '''This pipeline implements something similar to the following bash
        equivalent in Python: gst-launch-0.10 -vvv rtspsrc 
        location='rtsp://192.168.1.60:554/axis-media/
        media.amp?videocodec=jpeg&audio=0' ! rtpjpegdepay ! ffdec_mjpeg ! ...
        ! xvimagesink'''
        self.createEmptyPipeline()
        self.createPipelineElements()
        self.addElementsToPipeline()
        self.linkPipelineElements()
        self.createPipelineCallbacks()

    def createPipelineElements(self):
        self.createRtspsrcElement()
        self.createDepayElement()
        self.createDecodeElement()
        self.createCropElement()
        self.createVideoscaleElement()
        self.createVideorateElement()
        self.createVideobalanceElement()
        self.createCapsfilterElement()
        self.createFfmpegcolorspaceElement()
        self.createXvimagesinkElement()

    def addElementsToPipeline(self):
        '''Add elements to the pipeline'''
        self.pipeline.add(self.source)
        self.pipeline.add(self.depay)
        self.pipeline.add(self.decode)
        self.pipeline.add(self.crop)
        self.pipeline.add(self.videoscale)
        self.pipeline.add(self.videorate)
        self.pipeline.add(self.videobalance)
        self.pipeline.add(self.capsfilter)
        self.pipeline.add(self.ffmpegcolorspace)
        self.pipeline.add(self.xvimagesink)

    def linkPipelineElements(self):
        '''Link all elements in pipeline except source which has a dynamic
        source pad'''
        self.depay.link(self.decode)
        self.decode.link(self.crop)
        self.crop.link(self.videoscale)
        self.videoscale.link(self.videorate)
        self.videorate.link(self.videobalance)
        self.videobalance.link(self.capsfilter)
        self.capsfilter.link(self.ffmpegcolorspace)
        self.ffmpegcolorspace.link(self.xvimagesink)

class RtspPipelineToFileAndDisplay(RtspBaseClass):
    '''This class writes an rtsp stream to file and symultaneously displays the
    stream to an xvimagesink.  It is similar to the RtspPipelineToDisplay class
    with the addition of recording to file.'''
    
    def __init__(self, ipAddress, xid):
        self.ipAddress = ipAddress
        # xid is the xwindow I.D. where the video stream will be displayed:
        self.xid = xid
        self.createGstreamerPipeline()
        
    def createGstreamerPipeline(self):
        '''This pipeline implements something similar to the following bash
        equivalent in Python: gst-launch-0.10 -vvv rtspsrc 
        location='rtsp://192.168.1.60:554/axis-media/
        media.amp?videocodec=jpeg&audio=0' ! rtpjpegdepay ! ffdec_mjpeg ! ...
        ! xvimagesink'''
        self.createEmptyPipeline()
        self.createPipelineElements()
        self.addElementsToPipeline()
        self.linkPipelineElements()
        self.createPipelineCallbacks()
    
    def createPipelineElements(self):
        '''Create the elements required for the pipeline'''
        self.createRtspsrcElement()
        self.createDepayElement()
        self.createDecodeElement()
        self.createCropElement()
        self.createVideoscaleElement()
        self.createVideorateElement()
        self.createVideobalanceElement()
        self.createCapsfilterElement()
        self.createFfmpegcolorspaceElement()
        self.createTeeElement()
        self.createQueueFileElement()
        self.createQueueDisplayElement()
#        self.createTheoraencElement()
#        self.createOggmuxElement()
        self.createJpegencElement()
        self.createAvimuxElement()
        self.createFilesinkElement()
        self.createXvimagesinkElement()

    def addElementsToPipeline(self):
        '''Add the elements to the pipeline'''
        self.pipeline.add(self.source)
        self.pipeline.add(self.depay)
        self.pipeline.add(self.decode)
        self.pipeline.add(self.crop)
        self.pipeline.add(self.videoscale)
        self.pipeline.add(self.videorate)
        self.pipeline.add(self.videobalance)
        self.pipeline.add(self.capsfilter)
        self.pipeline.add(self.ffmpegcolorspace)
        self.pipeline.add(self.tee)
        self.pipeline.add(self.queueFile)
        self.pipeline.add(self.queueDisplay)
#        self.pipeline.add(self.theoraenc)
#        self.pipeline.add(self.oggmux)
        self.pipeline.add(self.jpegenc)
        self.pipeline.add(self.avimux)
        self.pipeline.add(self.filesink)
        self.pipeline.add(self.xvimagesink)

    def linkPipelineElements(self):
        '''Link all elements in pipeline except source which has a dynamic
        source pad'''
        self.depay.link(self.decode)
        self.decode.link(self.crop)
        self.crop.link(self.videoscale)
        self.videoscale.link(self.videorate)
        self.videorate.link(self.videobalance)
        self.videobalance.link(self.capsfilter)
        self.capsfilter.link(self.ffmpegcolorspace)
        self.ffmpegcolorspace.link(self.tee)
        self.tee.link(self.queueFile)
#        self.queueFile.link(self.theoraenc)
#        self.theoraenc.link(self.oggmux)
#        self.oggmux.link(self.filesink)
        self.queueFile.link(self.jpegenc)
        self.jpegenc.link(self.avimux)
        self.avimux.link(self.filesink)
        self.tee.link(self.queueDisplay)
        self.queueDisplay.link(self.xvimagesink)

class RtspPipelineLightenOnly(RtspBaseClass):
    '''This class displays an rtsp stream to the screen with brightness
    adjustment and no PTZ functions'''
    
    def __init__(self, ipAddress, xid):
        self.ipAddress = ipAddress
        # xid is the xwindow I.D. where the video stream will be displayed:
        self.xid = xid
        self.createGstreamerPipeline()
        
    def createGstreamerPipeline(self):
        '''This pipeline implements something similar to the following bash
        equivalent in Python: gst-launch-0.10 -vvv rtspsrc 
        location='rtsp://192.168.1.60:554/axis-media/
        media.amp?videocodec=jpeg&audio=0' ! rtpjpegdepay ! ffdec_mjpeg ! ...
        ! xvimagesink'''
        self.createEmptyPipeline()
        self.createPipelineElements()
        self.addElementsToPipeline()
        self.linkPipelineElements()
        self.createPipelineCallbacks()
    
    def createPipelineElements(self):
        '''Create the elements required for the pipeline'''
        self.createRtspsrcElement()
        self.createDepayElement()
        self.createDecodeElement()
        self.createVideobalanceElement()
        self.createXvimagesinkElement()

    def addElementsToPipeline(self):
        '''Add the elements to the pipeline'''
        self.pipeline.add(self.source)
        self.pipeline.add(self.depay)
        self.pipeline.add(self.decode)
        self.pipeline.add(self.videobalance)
        self.pipeline.add(self.xvimagesink)

    def linkPipelineElements(self):
        '''Link all elements in pipeline except source which has a dynamic
        source pad'''
        self.depay.link(self.decode)
        self.decode.link(self.videobalance)
        self.videobalance.link(self.xvimagesink)

class RtspPipelineSimple(RtspBaseClass):
    '''This class displays an rtsp stream to the screen with no PTZ or 
    brightness adjustment'''
    
    def __init__(self, ipAddress, xid):
        self.ipAddress = ipAddress
        # xid is the xwindow I.D. where the video stream will be displayed:
        self.xid = xid
        self.createGstreamerPipeline()
        
    def createGstreamerPipeline(self):
        '''This pipeline implements something similar to the following bash
        equivalent in Python: gst-launch-0.10 -vvv rtspsrc 
        location='rtsp://192.168.1.60:554/axis-media/
        media.amp?videocodec=jpeg&audio=0' ! rtpjpegdepay ! ffdec_mjpeg ! ...
        ! xvimagesink'''
        self.createEmptyPipeline()
        self.createPipelineElements()
        self.addElementsToPipeline()
        self.linkPipelineElements()
        self.createPipelineCallbacks()
    
    def createPipelineElements(self):
        '''Create the elements required for the pipeline'''
        self.createRtspsrcElement()
        self.createDepayElement()
        self.createDecodeElement()
        self.createXvimagesinkElement()

    def addElementsToPipeline(self):
        '''Add the elements to the pipeline'''
        self.pipeline.add(self.source)
        self.pipeline.add(self.depay)
        self.pipeline.add(self.decode)
        self.pipeline.add(self.xvimagesink)

    def linkPipelineElements(self):
        '''Link all elements in pipeline except source which has a dynamic
        source pad'''
        self.depay.link(self.decode)
        self.decode.link(self.xvimagesink)
