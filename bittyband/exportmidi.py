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
    def __init__(self, config, filenm):
        self.track = None
        self.filenm = filenm
        self.midifile = None

    def new_track(self, **kwargs):
        pass

    def unknown_track(self):
        pass

    def start(self):
        self.track = MidiTrack()
        self.midifile = MidiFile()
        self.midifile.tracks.append(self.track)

    def end(self):
        self.midifile.save(str(self.filenm))

    def player(self):
        pass

    def feed_comment(self, cmt, **kwargs):
        pass
    def feed_other(self, cmd, **kwargs):
        pass
    def sync_comment(self, cmt, **kwargs):
        pass

    def feed_lyric(self, lyric, **kwargs):
        pass

    def feed_midi(self, *what, ui=None, abbr=None, channel=None, time=None): 
        for w in what: 
            if time is not None:
                w.time = time
                time = None 
            self.track.append(w)

