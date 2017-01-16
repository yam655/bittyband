#!/usr/bin/env python3

import sys
import mido
import queue
import threading
import os.path
from datetime import datetime, timedelta
from mido import Message, MidiFile, MidiTrack

from .midinames import getLyForMidiNote, getLyForMidiDrum
from .commands import LEAD_CHANNEL, PAD_CHANNEL, DRUM_CHANNEL

LILYPOND_VERSION = "2.18.2"

_numbers_names = {"0": "Zero", "1":"One", "2":"Two", "3":"Three", "4":"Four",
"5":"Five", "6":"Six", "7":"Seven", "8":"Eight", "9":"Nine"}


class LilypondFile:
    title = None
    key = None
    file_comments = []
    header = []
    chords = []
    melody = []
    lyrics = []
    make_pdf = True
    make_midi = True
    clef = None
    bpm = None
    time_nu = None
    time_de = None

    def add_time(self, nu, de):
        if not self.melody:
            self.time_nu = nu
            self.time_de = de
        else:
            if self.time_de is None:
                self.add_chunk("\\candenzaOff", channel=LEAD_CHANNEL)
            if nu is None and de is not None:
                nu = de
            if de is None:
                self.add_chunk("\\candenzaOn", channel=LEAD_CHANNEL)
                self.time_nu = self.time_de = None
            else:
                self.time_nu = nu
                self.time_de = de
                self.add_chunk("    \\time {}/{}".format(self.time_nu, self.time_de), channel=LEAD_CHANNEL)

    def add_chunk(self, chunk, channel=None):
        if channel is None:
            self.header.append(chunk)
        elif channel == LEAD_CHANNEL:
            if len(self.melody) == 0 or not isinstance(self.melody[-1], list):
                self.melody.append(["r", 0, chunk])
            else:
                self.melody[-1].append(chunk)
        elif channel == PAD_CHANNEL:
            if len(self.chords) == 0 or not isinstance(self.chords[-1], list):
                self.chords.append(["r", 0, chunk])
            else:
                self.chords[-1].append(chunk)
        else:
            cmt = "%({}) {}".format(channel, chunk)
            self.file_comments.append(cmt)

    def __format__(self, fmt):
        global LILYPOND_VERSION
        result = []
        if LILYPOND_VERSION is not None:
            result.append('\\version "{}"'.format(LILYPOND_VERSION))
            result.append("")
        if self.file_comments:
            result.extend(self.file_comments)
            result.append("")
        result.append("\\header {")
        if self.title:
            titl = []
            titl.append("    title = \\markup {")
            for w in self.title.split():
                if w.isalnum():
                    titl.append(w)
                else:
                    titl.append('"{}"'.format(w.replace('"', '\\"')))
            titl.append("}")
            result.append(" ".join(titl))
            result.extend(self.header)
        result.append("}")
        result.append("")
        result.append("global = {")
        if self.time_nu and self.time_de:
            result.append("    \\time {}/{}".format(self.time_nu, self.time_de))
        if self.key:
            result.append("    \\key {}".format(self.key))
        if self.bpm:
            if self.time_de is None:
                result.append("    \\tempo {}={}".format(4, self.bpm))
            else:
                result.append("    \\tempo {}={}".format(self.time_de, self.bpm))
        result.append("}")
        result.append("")

        result.append("chordNames = {")
        result.append("    \\global")
        result.append("    \\set chordChanges = ##t")

        for n in self.chords:
            if isinstance(n, str):
                result.append(n)
            else:
                if n[1] > 0:
                    ch = lengthen_notes(n[0], n[1], self.time_nu, self.time_de)
                    if len(ch) == 1:
                        result.append("    {} % {} whole notes at 120 BPM".format(ch[0], n[1]))
                    else:
                        result.append(" ".join(ch))
                        result.append("            % {} whole notes at 120 BPM".format(n[1]))
                if len(n) > 2:
                    for c in n[2:]:
                        result.append("            {}".format(c))
        result.append("}")
        result.append("")

        result.append("melody = {")
        result.append("    \\global")
        for n in self.melody:
            if isinstance(n, str):
                result.append(n)
            else:
                if n[1] > 0:
                    ch = lengthen_notes(n[0], n[1], self.time_nu, self.time_de)
                    if len(ch) == 1:
                        result.append("    {} % {} whole notes at 120 BPM".format(ch[0], n[1]))
                    else:
                        result.append(" ".join(ch))
                        result.append("            % {} whole notes at 120 BPM".format(n[1]))
                if len(n) > 2:
                    for c in n[2:]:
                        result.append("            {}".format(c))
        result.append('            \\bar "|."')
        result.append("}")
        result.append("")

        for idx in range(len(self.lyrics)):
            sufx = number_suffix(idx + 1, len(self.lyrics))
            result.append("".join(["words", sufx, " = {"]))
            result.append('    \\set stanza = #"{}. "'.format(idx+1))
            for lne in self.lyrics[idx]:
                result.append('    {}'.format(lne))
            result.append("}")
            result.append("")

        result.append("\\score {")
        result.append("    <<")
        result.append("        \\new ChordNames \\chordNames")
        result.append("        \\new FretBoards \\chordNames")
        result.append("        \\new Staff \\new Voice \\with {")
        result.append('            \\remove "Note_heads_engraver"')
        result.append('            \\consists "Completion_heads_engraver"')
        result.append('            \\remove "Rest_engraver"')
        result.append('            \\consists "Completion_rest_engraver"')
        result.append("        } \\melody")

        for idx in range(len(self.lyrics)):
            sufx = number_suffix(idx + 1, len(self.lyrics))
            result.append("".join(["        \\addlyrics { \\words", sufx," }"]))
        result.append("    >>")
        if self.make_pdf:
            result.append("    \\layout { }")
        if self.make_midi:
            result.append("    \\midi { }")
        result.append("}")
        result.append("")
        return "\n".join(result)



class ExportLy:
    filenm = None
    nu = None
    de = None

    def __init__(self, config, filenm, title=None):
        self.filenm = filenm
        self.reconfigure(config)
        self.lily = LilypondFile()
        if title is not None:
            self.lily.title = title
        self.sync_count = 0
        self.lead_time = 0
        self.pad_time = 0

    def reconfigure(self, config):
        pass

    def start(self):
        pass

    def end(self):

        with self.filenm.open("wt") as out:
            out.write(format(self.lily))

    def player(self):
        pass

    def sync_comment(self, cmt):
        sync = "% [sync@{}] {}".format(self.sync_count, cmt)
        self.sync_count += 1
        self.lily.add_chunk(sync, channel=LEAD_CHANNEL)
        self.lily.add_chunk(sync, channel=PAD_CHANNEL)

    def feed_comment(self, cmt, channel=None):
        cmt = "% {}".format(cmt)
        if channel is None:
            self.lily.file_comments.append(cmt)
        else:
            self.lily.add_chunk(cmt, channel=channel)

    def _add_time(self, time):
        self.lead_time += time
        self.pad_time += time

    def feed_time(self, nu, de):
        if nu is None or de is None:
            self.nu = self.de = None
        elif self.nu != nu or self.de != de:
            self.lily.add_time(nu, de)

    def feed_other(self, cmd, channel=None):
        note = None
        if cmd == "rest":
            pass
        else:
            self.feed_comment(cmd, channel=channel)
            return

    def _feed_note(self, what_type, chunk, channel=None):
        if what_type == "note_on":
            if channel == LEAD_CHANNEL:
                if self.lead_time > 0:
                    self.lily.melody.append(["r", self.lead_time / 1000])
                    self.lead_time = 0
                self.lily.melody.append([chunk, 0])
            elif channel == PAD_CHANNEL:
                if self.pad_time:
                    self.lily.chords.append(["r", self.pad_time / 1000])
                    self.pad_time = 0
                self.lily.chords.append([chunk, 0])
            else:
                self.feed_comment("[{}] {}".format(what_type, chunk), channel=channel)
        elif what_type == "note_off":
            if channel == LEAD_CHANNEL:
                if len(self.lily.melody) > 0 and self.lily.melody[-1][1] == 0:
                    self.lily.melody[-1][1] = self.lead_time / 1000
                else:
                    self.lily.melody.append(["r", self.lead_time / 1000])
                self.lead_time = 0
            elif channel == PAD_CHANNEL:
                if len(self.lily.chords) > 0 and self.lily.chords[-1][1] == 0:
                    self.lily.chords[-1][1] = self.pad_time / 1000
                else:
                    self.lily.chords.append(["r", self.pad_time / 1000])
                self.pad_time = 0
            else:
                self.feed_comment("[{}] {}".format(what_type, chunk), channel=channel)
        else:
            self.feed_comment("[{}] {}".format(what_type, chunk), channel=channel)


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
        if channel == DRUM_CHANNEL:
            # can't manage this here
            return
        what_type = what[0].type

        chunk = None
        if what_type == "note_on":
            chunk = []
            if len(what) > 1:
                chunk.append("<")
            for w in what:
                chunk.append(" ")
                chunk.append(getLyForMidiNote(w.note))
            if len(what) > 1:
                chunk.append(" >")
            chunk = "".join(chunk).strip()
            self._feed_note(what_type, chunk, channel=channel)
        elif what_type == "note_off":
            self._feed_note(what_type, chunk, channel=channel)
        else:
            self.feed_comment("{!r}".format(what), channel=channel)


def lengthen_notes(note, r = 0.25, nu = 4, de = 4):
    ch = []
    nude = 1
    if nu is not None and de is not None:
        nude = nu / de
    if nude >= 1:
        while r > 0.8:
            if len(ch) == 0:
                ch.append("    {}1".format(note))
            else:
                ch.append(" ~ {}".format(note))
            r -= 1.0
    if nude >= 0.5:
        while r > 0.4:
            if len(ch) == 0:
                ch.append("    {}2".format(note))
            else:
                ch.append(" ~ {}2".format(note))
            r -= 0.5
    while r > 0.2:
        if len(ch) == 0:
            ch.append("    {}4".format(note))
        else:
            ch.append(" ~ {}4".format(note))
        r -= 0.25
    if r > 0.1:
        if len(ch) == 0:
            ch.append("    {}8".format(note))
        else:
            ch.append(" ~ {}8".format(note))
        r -= 0.125
    if r > 0:
        if len(ch) == 0:
            ch.append("    {}16".format(note))
        else:
            ch.append(" ~ {}16".format(note))
    return ch


def number_suffix(idx, totl):
    global _numbers_names
    if totl < 26:
        return chr(ord('A') + idx)
    ret = []
    for c in str(totl):
        if c in _numbers_names:
            ret.append(_numbers_names[c])
        else:
            ret.append(c)
    return "".join(ret)

