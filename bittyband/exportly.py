#!/usr/bin/env python3

__all__ = ["ExportLy"]

import sys
import mido
import queue
import threading
import os.path
from datetime import datetime, timedelta 
from mido import Message, MidiFile, MidiTrack

from .midinames import getLyForMidiNote
from .commands import LEAD_CHANNEL, PAD_CHANNEL

_template_p1 = r'''
\version "2.18.2"

\header {
    title = "'''

_template_p2 = r'''"
}

global = {
    \time 4/4
    \key c \major
    \tempo 4=120
}

chordNames = {
    \global
'''

_template_p3 = r''' 
}

melody = {
    \global
'''

_template_p4 = r'''
}

words = \lyricmode {
    
    
}

\score {
    <<
        \new ChordNames \chordNames
        \new FretBoards \chordNames
        \new Staff { \melody }
        \addlyrics { \words }
    >>
    \layout { }
    \midi { }
}
'''


class ExportLy:
    track = None
    filenm = None
    title = ""

    def __init__(self, config, filenm, title=""):
        self.filenm = filenm
        self.reconfigure(config)
        if title is not None:
            self.title = title

    def reconfigure(self, config):
        pass

    def start(self):
        self.global_blocks = []
        self.lead_blocks = []
        self.pad_blocks = []
        self.sync_count = 0
        self.lead_time = 0
        self.pad_time = 0

    def end(self):
        global _template_p1
        global _template_p2
        global _template_p3
        global _template_p4

        with self.filenm.open("wt") as out:
            out.write(_template_p1)
            out.write(self.title)
            out.write(_template_p2)
            out.write("".join(self.pad_blocks))
            out.write(_template_p3)
            out.write("".join(self.lead_blocks))
            out.write(_template_p4)

    def player(self):
        pass

    def sync_comment(self, cmt):
        sync = " % [sync@{}] ".format(self.sync_count)
        self.sync_count += 1
        self.lead_blocks.append(sync)
        self.lead_blocks.append(cmt)
        self.lead_blocks.append("\n")
        self.pad_blocks.append(sync)
        self.pad_blocks.append(cmt)
        self.pad_blocks.append("\n")

    def feed_comment(self, cmt, channel=None):
        if channel is None:
            self.global_blocks.append(" % ")
            self.global_blocks.append(cmt)
            self.global_blocks.append("\n")
        elif channel == LEAD_CHANNEL:
            self.lead_blocks.append(" % ")
            self.lead_blocks.append(cmt)
            self.lead_blocks.append("\n")
        elif channel == PAD_CHANNEL:
            self.pad_blocks.append(" % ")
            self.pad_blocks.append(cmt)
            self.pad_blocks.append("\n")
        else:
            self.global_blocks.append(" %({}) ".format(channel))
            self.global_blocks.append(cmt)

    def feed_other(self, cmd, channel=None):
        if cmd == "rest":
            cmd = " r"
        if channel is None:
            self.global_blocks.append(cmd)
            self.global_blocks.append("\n")
        elif channel == LEAD_CHANNEL:
            self.lead_blocks.append(cmd)
            self.lead_blocks.append("\n")
        elif channel == PAD_CHANNEL:
            self.pad_blocks.append(cmd)
            self.pad_blocks.append("\n")
        else:
            self.global_blocks.append(cmd)
            self.global_blocks.append(" % ({})\n".format(channel))

    def _add_time(self, time):
        self.lead_time += time
        self.pad_time += time

    def feed_midi(self, *what, ui=None, abbr=None, channel=None, time=None):
        if len(what) == 0:
            return
        if abbr == "panic":
            self.sync_comment("all notes off")
            return
        if channel is None:
            channel = what[0].channel
        if time is None:
            time = what[0].time
        else:
            what[0].time = time
        self._add_time(time)

        what_type = what[0].type

        chunk = [] 
        if what_type == "note_on": 
            if len(what) > 1:
                chunk.append(" < ")
            for w in what:
                chunk.append(getLyForMidiNote(w.note))
            if len(what) > 1:
                chunk.append(" > ")
        elif what_type == "note_off": 
            chunk.append(" % {:.4} whole notes at 120 BPM\n".format(time / 1000))
        else:
            chunk.append(" % {!r}\n".format(what))
            
        if channel == LEAD_CHANNEL: 
            self.lead_blocks.extend(chunk)
            if what_type == "note_off": 
                self.lead_time = 0
        elif channel == PAD_CHANNEL:
            self.pad_blocks.extend(chunk)
            if what_type == "note_off": 
                self.pad_time = 0
        else:
            self.global_blocks.append(cmd)
            self.global_blocks.append(" % ({})\n".format(channel))

