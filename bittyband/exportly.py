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

chordNames = \chordmode {
    \global
    
}

melody = {
    \global
'''

_template_p3 = r'''
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
        global _template_p1
        global _template_p2
        self.blocks = [_template_p1, self.title, _template_p2]

    def end(self):
        global _template_p3
        self.blocks.append(_template_p3)
        self.filenm.write_text("".join(self.blocks))

    def player(self):
        pass

    def feed_midi(self, what, ui=None):
        if what.type == "note_on":
            self.blocks.append(getLyForMidiNote(what.note))
        elif what.type == "note_off":
            self.blocks.append(" % {:.4} whole notes at 120 BPM\n".format(what.time / 1000))

