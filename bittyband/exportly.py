#!/usr/bin/env python3

import sys
import mido
import queue
import threading
import os.path
from datetime import datetime, timedelta
from mido import Message, MidiFile, MidiTrack

from pathlib import Path

from .midinames import getLyForMidiNote, getMidiInstrumentName
from .commands import LEAD_CHANNEL, PAD_CHANNEL, DRUM_CHANNEL
from .utils.cmdutils import *

LILYPOND_VERSION = "2.18.2"

_numbers_names = {"0": "Zero", "1":"One", "2":"Two", "3":"Three", "4":"Four",
"5":"Five", "6":"Six", "7":"Seven", "8":"Eight", "9":"Nine"}


class LilypondFile:
    def __init__(self):
        self.title = None
        self.key = None
        self._file_comments = []
        self.header = []
        self.chords = []
        self.melody = []
        self.lyrics = []
        self.make_pdf = True
        self.make_midi = True
        self.clef = None
        self.bpm = None
        self.time_nu = None
        self.time_de = None
        self.poet = None
        self.copyright = None
        self.tagline = None
        self.filename = None

    def is_empty(self):
        empty = True
        for m in self.melody:
            if len(m) == 2 and m[-1] > 0:
                empty = False
        for c in self.chords:
            if len(c) == 2 and c[-1] > 0:
                empty = False
        return empty and not self.lyrics

    def add_time(self, nu, de):
        if not self.melody:
            self.time_nu = int(nu)
            self.time_de = int(de)
        else:
            if self.time_de is None:
                self.add_chunk("\\candenzaOff", channel=LEAD_CHANNEL)
            if nu is None and de is not None:
                nu = de
            if de is None:
                self.add_chunk("\\candenzaOn", channel=LEAD_CHANNEL)
                self.time_nu = self.time_de = None
            else:
                self.time_nu = int(nu)
                self.time_de = int(de)
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
            self._file_comments.append(cmt)

    def _markup(self, what, text):
        ret = ["   ", what, "= \markup {"]
        if text is not None:
            for w in text.split():
                ret.append(quote_as_needed(w))
        ret.append("}")
        return " ".join(ret)

    def __format__(self, fmt):
        global LILYPOND_VERSION
        result = []
        if LILYPOND_VERSION is not None:
            result.append('\\version "{}"'.format(LILYPOND_VERSION))
            result.append("")
        if self._file_comments:
            result.extend(self._file_comments)
            result.append("")
        result.append("\\header {")
        result.append(self._markup("title", self.title))
        result.append(self._markup("poet", self.poet))
        result.append(self._markup("copyright", self.copyright))
        if self.tagline:
            result.append(self._markup("tagline", self.tagline))
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
                        # result.append("    {} % {} 1/4 notes at {} BPM".format(ch[0], n[1], self.bpm))
                        result.append("    {}".format(ch[0]))
                    else:
                        result.append(" ".join(ch))
                        # result.append("            % {} 1/4 notes at {} BPM".format(n[1], self.bpm))
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
                        result.append("    {}".format(ch[0]))
                        # result.append("    {} % {} 1/4 notes at {} BPM".format(ch[0], n[1], self.bpm))
                    else:
                        result.append(" ".join(ch))
                        # result.append("            % {} 1/4 notes at {} BPM".format(n[1], self.bpm))

                if len(n) > 2:
                    for c in n[2:]:
                        result.append("            {}".format(c))
        result.append('            \\bar "|."')
        result.append("}")
        result.append("")

        if self.lyrics:
            if isinstance(self.lyrics[0], str):
                result.append("words = \\lyricmode {")
                result.append('%    \\set stanza = #"1. "')
                for lne in " ".join(self.lyrics).split("\n"):
                    result.append('    {}'.format(lne))
                result.append("}")
                result.append("")
            else:
                for idx in range(len(self.lyrics)):
                    sufx = number_suffix(idx + 1, len(self.lyrics))
                    result.append("".join(["words", sufx, " = {"]))
                    result.append('%    \\set stanza = #"{}. "'.format(idx+1))
                    for lne in " ".join(self.lyrics[idx]).split("\n"):
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

        if self.lyrics:
            if isinstance(self.lyrics[0], str):
                result.append("".join(["        \\addlyrics { \\words }"]))
            else:
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
        self.lilies = []
        self.new_track(title=title)
        self.sync_count = 0
        self.lead_time = 0
        self.pad_time = 0

    def reconfigure(self, config):
        pass

    def start(self):
        pass

    def end(self):
        usable = []
        for lil in self.lilies:
            if not lil.is_empty():
                usable.append(lil)
        if len(usable) == 1:
            with self.filenm.open("wt") as out:
                out.write(format(usable[0]))
        else:
            i = 0
            for lily in usable:
                i += 1
                if lily.filename is None:
                    filename = self.filenm.with_name("{}-{}{}".format(self.filenm.stem, i, self.filenm.suffix))
                else:
                    filename = self.filenm.joinpath(lily.filename)
                with filename.open("wt") as out:
                    out.write(format(lily))

    def new_track(self, *, bpm = 120, lily_key = r"c \major", copyright = None, tagline = None, poet=None,
                  time="common", title, filename = None, **kwargs):
        self.lily = LilypondFile()
        self.lilies.append(self.lily)
        self.lily.bpm = bpm
        self.beat = mido.bpm2tempo(int(bpm)) / 1000
        t = parse_timing(time)
        if t is not None:
            t = t.split("/")
            self.lily.time_nu = int(t[0])
            self.lily.time_de = int(t[1])
        self.lily.title = title
        self.lily.poet = poet
        self.lily.key = lily_key
        self.lily.copyright = copyright
        self.lily.tagline = tagline
        self.lily.filename = filename

    def unknown_track(self):
        self.lily = self.lilies[0]

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
            self.lily._file_comments.append(cmt)
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

    def _feed_instrument(self, cmd, *, channel):
        lilyinstr = getMidiInstrumentName(cmd.program)
        if lilyinstr is None or lilyinstr == "":
            self.feed_comment("Unknown MIDI Instrument numbered {}".format(cmd.program), channel=channel)
        else:
            self.lily.add_chunk('\\set midiInstrument = #"{}"'.format(lilyinstr.lower()), channel=channel)

    def _feed_note(self, what_type, chunk, channel=None):
        if what_type == "note_on":
            if channel == LEAD_CHANNEL:
                if self.lead_time > 0:
                    self.lily.melody.append(["r", self.lead_time / self.beat])
                    self.lead_time = 0
                self.lily.melody.append([chunk, 0])
            elif channel == PAD_CHANNEL:
                if self.pad_time > 0:
                    self.lily.chords.append(["r", self.pad_time / self.beat])
                    self.pad_time = 0
                self.lily.chords.append([chunk, 0])
            else:
                self.feed_comment("[{}] {}".format(what_type, chunk), channel=channel)
        elif what_type == "note_off":
            if channel == LEAD_CHANNEL:
                if len(self.lily.melody) > 0 and self.lily.melody[-1][1] == 0:
                    self.lily.melody[-1][1] = self.lead_time / self.beat
                else:
                    self.lily.melody.append(["r", self.lead_time / self.beat])
                self.lead_time = 0
            elif channel == PAD_CHANNEL:
                if len(self.lily.chords) > 0 and self.lily.chords[-1][1] == 0:
                    self.lily.chords[-1][1] = self.pad_time / self.beat
                else:
                    self.lily.chords.append(["r", self.pad_time / self.beat])
                self.pad_time = 0
            else:
                self.feed_comment("[{}] {}".format(what_type, chunk), channel=channel)
        else:
            self.feed_comment("[{}] {}".format(what_type, chunk), channel=channel)


    def feed_lyric(self, lyric):
        if lyric is None or lyric == "":
            return
        if lyric.startswith("/"):
            self.lily.lyrics.append("\n")
            lyric = lyric[1:]
        elif lyric.startswith("\\"):
            self.lily.lyrics.append("\n\n")
            lyric = lyric[1:]
        if lyric.endswith(" --"):
            self.lily.lyrics.append(quote_as_needed(lyric[:-3]))
            self.lily.lyrics.append("--")
        elif lyric.endswith(" __"):
            self.lily.lyrics.append(quote_as_needed(lyric[:-3]))
            self.lily.lyrics.append("__")
        else:
            self.lily.lyrics.append(quote_as_needed(lyric))

    def feed_midi(self, *what, abbr=None, channel=None, time=None):
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
        elif what_type == "program_change":
            self._feed_instrument(what[0], channel=channel)
        else:
            self.feed_comment("{!r}".format(what), channel=channel)


def lengthen_notes(note, r = 1, nu = 4, de = 4):
    ch = []
    nude = 1
    if nu is not None and de is not None:
        nude = nu / de
    r = r / 4
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

def quote_as_needed(text):
    if text.isalpha():
        return text
    return '"{}"'.format(text.replace("\\","\\\\").replace('"', r'\"'))
