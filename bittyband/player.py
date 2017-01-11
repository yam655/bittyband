#!/usr/bin/env python3

__all__ = ["PushButtonPlayer"]

import sys
import mido
import queue
import threading
import os.path
from datetime import datetime, timedelta 
from mido import Message, MidiFile, MidiTrack

class PushButtonPlayer:

    def __init__(self, config):
        self.queue = queue.Queue() 
        self.thread = None
        self.active = {}
        self.reconfigure(config)
        self.ui = None

    def __del__(self):
        self.end()

    def reconfigure(self, config):
        self.midiport = None
        if "project" in config:
            self.midiport = config["instance"].get("midiport")

    def start(self):
        if self.thread is None:
            self.thread = threading.Thread(target=self.player)
            self.thread.start()

    def end(self):
        if self.queue is not None and self.thread is not None:
            self.queue.join()
            self.queue.put(None)

    def player(self):
        with mido.open_output(self.midiport) as output:
            while True:
                message = self.queue.get()
                if message is None:
                    break
                output.send(message)
                self.queue.task_done()
        self.thread = None
        self.queue = None

    def feed_comment(self, cmt, **kwargs):
        pass
    def feed_other(self, cmd, **kwargs):
        pass
    def sync_comment(self, cmt, **kwargs):
        pass

    def feed_midi(self, *what, ui=None, abbr=None, channel=None, time=None): 
        self.ui = ui
        if self.queue is not None:
            for w in what:
                if time is not None:
                    w.time = time
                    time = None
                self.queue.put(w)

