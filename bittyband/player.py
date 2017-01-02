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
        self.close()

    def reconfigure(self, config):
        self.portname = config["project"].get("portname")

    def open(self):
        if self.thread is None:
            self.thread = threading.Thread(target=self.player)
            self.thread.start()

    def close(self):
        if self.queue is not None and self.thread is not None:
            self.queue.join()
            self.queue.put(None)

    def player(self):
        with mido.open_output(self.portname) as output:
            while True:
                message = self.queue.get()
                if message is None:
                    break
                output.send(message)
        self.thread = None

    def feed_midi(self, what, ui=None):
        self.ui = ui
        self.queue.put(what)

