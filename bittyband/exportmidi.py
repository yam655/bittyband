#!/usr/bin/env python3

__all__ = ["ExportMidi"]

import sys
import mido
import queue
import threading
import os.path
from datetime import datetime, timedelta 
from mido import Message, MidiFile, MidiTrack

class ExportMidi:
    track = None
    filenm = None

    def __init__(self, config, filenm):
        self.filenm = filenm
        self.reconfigure(config)

    def reconfigure(self, config):
        pass

    def start(self):
        self.track = MidiTrack()
        self.midifile = MidiFile()
        self.midifile.tracks.append(self.track)

    def end(self):
        self.midifile.save(str(self.filenm))

    def player(self):
        pass

    def feed_midi(self, what, ui=None):
        self.track.append(what)

