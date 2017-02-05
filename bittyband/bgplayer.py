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
DRUM_VELOCITY=16

class BackgroundDrums:

    def __init__(self, config):
        self.queue = queue.Queue() 
        self.thread = None
        self.active = {}
        self.ui = None
        track = MidiTrack()
        self.midifile = MidiFile()
        self.midifile.tracks.append(track)

    def wire(self, *, push_player, **kwargs):
        self.player = push_player

    def __del__(self):
        self.end()

    def start(self):
        if self.thread is None:
            self.thread = threading.Thread(target=self.runner, daemon=True)
            self.thread.start()
            self.pause()

    def end(self):
        if self.queue is not None and self.thread is not None:
            self.queue.join()
            self.queue.put(None)

    def runner(self):
        terminate = False
        while not terminate:
            try:
                for midi in self.midifile.play():
                    if not self.queue.empty():
                        while True:
                            message = self.queue.get()
                            self.queue.task_done()
                            if message is None:
                                terminate = True
                                raise InterruptedError
                            if isinstance(message, str):
                                if message == "restart" or message == "start":
                                    raise InterruptedError
                                elif message == "pause":
                                    pass
                                elif message == "resume" or message == "play":
                                    break
                    self.player.feed_midi(midi)
            except InterruptedError:
                pass
        self.thread = None
        self.queue = None

    def set_tempo(self, num, dem, tempo): 
        hihat = getNoteForName("hihat")
        pedalhihat = getNoteForName("pedalhihat")
        bassdrum = getNoteForName("bassdrum")
        snare = getNoteForName("snare")
        sn = getNoteForName("sn")
        ss = getNoteForName("ss")
        #a0 = "hh hh // hhp // bd"
        #b0 = "hh hh // hhp // sn"
        #c0 = "hh hh // hhp // bd bd"
        #seq0 = "abcb"
        a = [[hihat, hihat], pedalhihat, bassdrum]
        b = [[hihat, hihat], pedalhihat, snare]
        c = [[hihat, hihat], pedalhihat, [bassdrum, bassdrum]]
        s = [ss, ss, ss, ss]
        seq = [s, s, s, s]
        self.set_pattern(num, dem, tempo, *seq)

    def set_pattern(self, num, dem, tempo, *seq):
        global DRUM_CHANNEL
        global DRUM_VELOCITY
        track = MidiTrack()
        newMidifile = MidiFile()
        newMidifile.tracks.append(track)
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
                            notebucket.append(Message("note_on", channel=DRUM_CHANNEL, note=note, velocity=DRUM_VELOCITY, time= basetime + (mytempo * i)))
                            notebucket.append(Message("note_off", channel=DRUM_CHANNEL, note=note, time=basetime + (mytempo * (i + 1))))
                    else:
                        notebucket.append(Message("note_on", channel=DRUM_CHANNEL, note=items, velocity=DRUM_VELOCITY, time=basetime))
                        notebucket.append(Message("note_off", channel=DRUM_CHANNEL, note=items, time=basetime + basetempo) )
            else:
                if s > 0:
                    notebucket.append(Message("note_on", channel=DRUM_CHANNEL, note=s, velocity=DRUM_VELOCITY, time=basetime))
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
            track.append(evt)
        self.midifile = newMidifile

    def pause(self):
        self.queue.put("pause")

    def resume(self):
        self.queue.put("resume")

    def stop(self):
        self.queue.put("stop")

    def play(self):
        self.queue.put("play")

    def rewind(self):
        self.queue.put("restart")

class BackgroundNull:

    def __init__(self, config = None, player = None):
        pass

    def wire(self, *, push_player, **kwargs):
        pass

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

    def pause(self):
        pass

    def resume(self):
        pass

    def stop(self):
        pass

    def play(self):
        pass

    def rewind(self):
        pass

