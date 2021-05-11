# -*- coding: utf-8 -*-
"""
@author: Rafael G. de Paulo (github.com/rafael-g-depaulo)
@author: Lucas Vinícius Magalhães Pinheiro (github.com/LucasVinic)

@description: PyDash Project

An implementation example of a R2A Algorithm built to minimize video buffering.

the quality list is obtained with the parameter of handle_xml_response() method and the choice
is made inside of handle_segment_size_request(), before sending the message down.

In this algorithm the quality chosen is made to keep the client video buffer stable, using the
client's bandwith properly while trying to minimize the chance of buffering.

If the current buffer is below target ammount of segments, decrese target quality. If the
current buffer is above target ammount of segments, increase target quality.
"""

from player.parser import *
from r2a.ir2a import IR2A
from base.whiteboard import Whiteboard
import time

class R2ABufferOriented(IR2A):

    def __init__(self, id):
        IR2A.__init__(self, id)
        self.parsed_mpd = ''
        self.qi = []
        # request time
        self.request_time = 0
        # ammount of segments recieved
        self.recievedSegments = 0
        # dynamic estimated channel throughput
        self.throughput = 0
        # buffer size when the last segment was requested
        self.oldBufferSize = 0
        # algorithm parameters
        self.bufferTarget = 20
        self.maxBufferDrop = 4
        self.initialMultiplier = 0.75
        self.decreaseAmmount = 0.95
        self.increaseAmmount = 1.02

    def handle_xml_request(self, msg):
        self.request_time = time.perf_counter()
        print('')
        print(f'>>>>>>>> requesting XML. current time {self.request_time}')
        print('')
        self.send_down(msg)

    def handle_xml_response(self, msg):
        # getting qi list
        self.parsed_mpd = parse_mpd(msg.get_payload())
        self.qi = self.parsed_mpd.get_qi()

        # get time between request and response
        rtt = time.perf_counter() - self.request_time
        # set estimated throughput based on segment size and rtt
        self.throughput = (msg.get_bit_length() / rtt)

        print('')
        print(f'>>>>>>>> recieved XML response. current time {time.perf_counter()}')
        print(f'>>>>>>>> rtt: {rtt}')
        print(f'>>>>>>>> msg length: {msg.get_bit_length()}')
        print(f'>>>>>>>> estimated throughput: {self.throughput}')
        print('')

        self.send_up(msg)

    def handle_segment_size_request(self, msg):
        print('')
        print('>>>>>>>> chosing segment quality')
        
        # initialize desiredQuality
        desiredQuality = 0
        # get buffer size
        bufferSize = self.get_buffer_size()

        print(f'>>>>>>>> current buffer size: {bufferSize}. old buffer size {self.oldBufferSize}')

        # at the start of the video, maintain quality stable until enough segments have been recieved to start judging the buffer length
        if self.recievedSegments == 0:
            print('>>>>>>>> requesting first segment')
            desiredQuality = self.throughput * self.initialMultiplier

        elif self.recievedSegments < self.bufferTarget:
            desiredQuality = self.throughput

        # if buffer above target and is decreasing rapidly, decrease quality instead of increasing
        elif (bufferSize >= self.bufferTarget) and (self.oldBufferSize - bufferSize > self.maxBufferDrop):
            oldQuality = self.throughput
            decreaseFactor = self.decreaseAmmount ** (self.oldBufferSize - bufferSize)
            desiredQuality = self.throughput = self.throughput * decreaseFactor
            print(f'>>>>>> buffer is above target by {bufferSize}, but it went down {self.oldBufferSize - bufferSize} segments since the last segment request. quality decreased from {oldQuality} to {desiredQuality}')

        # if buffer is below target, decrease quality
        elif bufferSize < self.bufferTarget:
            oldQuality = self.throughput
            decreaseFactor = self.decreaseAmmount ** (self.bufferTarget - bufferSize)
            desiredQuality = self.throughput = self.throughput  * decreaseFactor
            print(f'>>>>>>>> buffer is below target by ({self.bufferTarget - bufferSize}). decrease desired quality from {oldQuality} to {desiredQuality} (x{decreaseFactor})')

        # if buffer is at target, keep at current quality
        elif bufferSize == self.bufferTarget:
            desiredQuality = self.throughput
            print(f'>>>>>>>> buffer is stable. keep at current quality')

        # if buffer is above target increase quality
        elif bufferSize > self.bufferTarget:
            oldQuality = self.throughput
            increaseFactor = (self.increaseAmmount ** (bufferSize - self.bufferTarget))
            # increaseFactor = self.increaseAmmount
            desiredQuality = self.throughput = max(self.throughput * increaseFactor, self.qi[0])
            print(f'>>>>>>>> buffer is above target by ({bufferSize - self.bufferTarget}). increase desired quality from {oldQuality} to {desiredQuality} (x{increaseFactor})')
        
        # select largest quality below target maximum
        self.oldBufferSize = bufferSize
        selected_qi = self.get_closest_quality(desiredQuality)
        print(f'>>>>>>>> desired quality: {desiredQuality}')
        print(f'>>>>>>>> selected quality: {selected_qi}')

        msg.add_quality_id(selected_qi)

        print('')
        self.send_down(msg)

    def handle_segment_size_response(self, msg):
        self.recievedSegments += 1
        self.send_up(msg)

    def get_buffer_size(self):
        wboard = Whiteboard.get_instance()
        playbackBuffer = wboard.get_playback_buffer_size()
        bufferSize = playbackBuffer[-1][1] - 1 if len(playbackBuffer) > 0 else 0
        return bufferSize
    
    def get_closest_quality(self, desiredQuality):
        selected_qi = self.qi[0]
        for i in self.qi:
            if desiredQuality >= i:
                selected_qi = i
        return selected_qi

    def initialize(self):
        pass

    def finalization(self):
        pass
