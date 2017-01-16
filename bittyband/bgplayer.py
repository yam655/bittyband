#!/usr/bin/env python3

__all__ = ["BackgroundDrums", "BackgroundNull"]

import sys
import mido
import queue
import threading
import os.path
from datetime import datetime, timedelta 
from mido import Message, MidiFile, MidiTrack

from .midinames import *
from .errors import *

DRUM_CHANNEL=9

class BackgroundDrums:

    def __init__(self, config):
        self.queue = queue.Queue() 
        self.thread = None
        self.active = {}
        self.ui = None
        self.paused = True
        self.midifile = None

    def wire(self, *, push_player, **kwargs):
        self.player = push_player

    def __del__(self):
        self.end()

    def start(self):
        if self.thread is None:
            self.thread = threading.Thread(target=self.runner, daemon=True)
            self.thread.start()

    def end(self):
        if self.queue is not None and self.thread is not None:
            self.queue.join()
            self.queue.put(None)

    def runner(self):
        terminate = False
        midifile = None
        while not terminate:
            if midifile is None:
                terminate, br = self._process_queue()
            midifile = self.midifile
            if midifile is not None:
                for midi in midifile.play():
                    self.player.feed_midi(midi)
                    if not self.queue.empty():
                        terminate, br = self._process_queue()
                        while self.paused:
                            terminate, br = self._process_queue()
                            if terminate or br:
                                break
                        if terminate or br:
                            break
        self.thread = None
        self.queue = None

    def _process_queue(self):
        message = self.queue.get()
        self.queue.task_done()
        if message is None:
            return (True, True)
        if isinstance(message, str):
            if message == "restart" or message == "start":
                self.paused = False
                return (False, True)
            elif message == "pause_resume":
                if self.paused:
                    self.paused = False
                    return (False, False)
                term = br = True
                self.paused = True
            elif message == "pause":
                self.paused = True
            elif message == "resume":
                self.paused = False
        return (False, False)

    def set_tempo(self, num, dem, tempo): 
        hihat = getNoteForName("hihat")
        pedalhihat = getNoteForName("pedalhihat")
        bassdrum = getNoteForName("bassdrum")
        snare = getNoteForName("snare")
        #a0 = "hh hh // hhp // bd"
        #b0 = "hh hh // hhp // sn"
        #c0 = "hh hh // hhp // bd bd"
        #seq0 = "abcb"
        a = [[hihat, hihat], pedalhihat, bassdrum]
        b = [[hihat, hihat], pedalhihat, snare]
        c = [[hihat, hihat], pedalhihat, [bassdrum, bassdrum]]
        seq = [a, b, c, b, c, a]
        self.set_pattern(num, dem, tempo, *seq)

    def set_pattern(self, num, dem, tempo, *seq):
        global DRUM_CHANNEL
        self.track = MidiTrack()
        self.midifile = MidiFile()
        self.midifile.tracks.append(self.track) 
        nexttime = 0
        notebucket = []
        basetime = 0
        basetempo = tempo * 4 / dem
        for si in range(num):
            s = seq[si % len(seq)]
            if hasattr(s, "__iter__"):
                for items in s:
                    if hasattr(items, "__iter__"):
                        mytempo = basetempo / len(items)
                        for i in range(len(items)):
                            note = items[i]
                            notebucket.append(Message("note_on", channel=DRUM_CHANNEL, note=note, time= basetime + (mytempo * i)))
                            notebucket.append(Message("note_off", channel=DRUM_CHANNEL, note=note, time=basetime + (mytempo * (i + 1))))
                    else:
                        notebucket.append(Message("note_on", channel=DRUM_CHANNEL, note=items, time=basetime))
                        notebucket.append(Message("note_off", channel=DRUM_CHANNEL, note=items, time=basetime + basetempo) )
            else:
                if s > 0:
                    notebucket.append(Message("note_on", channel=DRUM_CHANNEL, note=s, time=basetime))
                    notebucket.append(Message("note_off", channel=DRUM_CHANNEL, note=s, time=basetime + basetempo))
            basetime += basetempo
        notebucket.sort(key=lambda message: message.time)
        start = None
        for evt in notebucket:
            if start is None:
                start = evt.time
                evt.time = 0
            else:
                n = evt.time
                evt.time = (n - start) / 1000
                start = n
            self.track.append(evt)

    def play_pause(self):
        self.queue.put("play-pause")

    def pause(self):
        self.queue.put("pause")

    def is_stopped(self):
        return self.paused

    def rewind(self):
        self.queue.put("restart")

class BackgroundNull:

    def __init__(self, config = None, player = None):
        self.paused = True

    def start(self):
        pass

    def end(self):
        pass

    def runner(self):
        pass

    def set_tempo(self, num, dem, tempo):
        pass

    def set_pattern(self, num, dem, tempo, *seq):
        pass

    def play_pause(self):
        if self.paused:
            self.paused = False
        else:
            self.paused = True
        return self.paused

    def pause(self):
        self.paused = True

    def is_stopped(self):
        return self.paused

    def rewind(self):
        pass

