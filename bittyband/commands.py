#!/usr/bin/env python3

__all__ = ["Commands", "LEAD_CHANNEL", "PAD_CHANNEL"]

import sys
from mido import Message

from .config import ConfigError
from .midinames import getLyForMidiNote
import time

import locale
locale.setlocale(locale.LC_ALL, '')
code = locale.getpreferredencoding()

OCTAVE_STEPS = 12
LEAD_CHANNEL = 0
PAD_CHANNEL = 1


class Commands:
    config = None 
    lead_chords = [0, 2, 4]
    pad_chords = [0, 2, 4]
    pad_chord_idx = -1
    pad_chord_seq = []
    scale = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    active_preset = None 
    lead_note = None
    pad_note = None
    key_note = 60
    pad_instrument = 0
    lead_instrument = 0
    ui = None
    message_time = 0

    def __init__(self, config, player, cmdrecorder):
        self.config = config
        self.player = player
        self.cmdrecorder = cmdrecorder

    def execute(self, cmd, ui=None):
        global action_mapping
        self.ui = ui
        action = action_mapping.get(cmd)
        if action is not None:
            action(self, cmd)

    def play(self, material, realtime=True):
        global action_mapping
        start = None
        end = None
        for line in material:
            if line[0] in "# \t":
                continue
            p = line.split(",",1)
            cmd = p[-1]
            end = float(p[0])
            if start is not None:
                s = (end-start)
                if s > 0:
#                   self.message_time = int(s * 1000000)
                    self.message_time = int(s * 1000)
                    if realtime:
                        time.sleep(s)
            if cmd[0] == "!":
                continue
            action = action_mapping.get(cmd)
            if action is not None:
                action(self, cmd)
            start = end
        self.do_silence("silence")

    def do_nothing(self, what):
        pass

    def do_chord_prev(self, what):
        if len(self.pad_chord_seq) == 0:
            return
        self.pad_chord_idx -= 1
        if self.pad_chord_idx < 0:
            self.pad_chord_idx = len(self.pad_chord_seq) - 1
        self.player.sync_comment("changing to previous chord")
        self.set_pad_note(self.pad_chord_seq[self.pad_chord_idx])
    def do_chord_next(self, what):
        if len(self.pad_chord_seq) == 0:
            return
        self.pad_chord_idx += 1
        if self.pad_chord_idx >= len(self.pad_chord_seq):
            self.pad_chord_idx = 0
        self.player.sync_comment("changing to next chord")
        self.set_pad_note(self.pad_chord_seq[self.pad_chord_idx])
    def do_chord_repeat(self, what):
        if len(self.pad_chord_seq) == 0:
            return
        self.player.sync_comment("repeating chord")
        self.set_pad_note(self.pad_chord_seq[self.pad_chord_idx])

    def do_preset(self, what):
        global LEAD_CHANNEL
        global PAD_CHANNEL
        if what is None:
            return

        self.pad_chord_idx = -1
        self.pad_chord_seq = []
        title = self.config[what]["title"]
        midi_set = []
        if self.ui is not None:
            if title is not None:
                self.ui.putln("\nPreset Setting to: {}".format(title))
                if self.cmdrecorder is not None:
                    self.cmdrecorder.add("!set title={}".format(title))
            else:
                self.ui.putln("\nPreset Setting to: {}".format(what))
        if title is not None:
            self.player.feed_comment(title)

        if "key" in self.config[what]:
            self.key_note = int(self.config[what]["key"])
            self.player.feed_comment("key note: {}".format(getLyForMidiNote(self.key_note)))
        if self.cmdrecorder is not None:
            self.cmdrecorder.add("!set key={0!r}".format(self.key_note))
        if "scale" in self.config[what]:
            self.scale = parse_scale(self.config[what]["scale"].strip())
            self.player.feed_comment("scale contents: {!r}".format(self.scale))
        if self.cmdrecorder is not None:
            self.cmdrecorder.add("!set scale={0!r}".format(self.scale))
        if "lead_instrument" in self.config[what]:
            self.lead_instrument = int(self.config[what]["lead_instrument"])
        else:
            self.lead_instrument = 0

        self.player.feed_midi(Message('program_change', channel=LEAD_CHANNEL,
                            program=self.lead_instrument, time=self.message_time))
        self.message_time = 0
        if self.cmdrecorder is not None:
            self.cmdrecorder.add("!set lead_instrument={0!r}".format(self.lead_instrument))
        if "pad_instrument" in self.config[what]:
            self.pad_instrument=int(self.config[what]["pad_instrument"])
        else:
            self.pad_instrument = 0
        self.player.feed_midi(Message('program_change', channel=PAD_CHANNEL,
                            program=self.pad_instrument, time=0))
        if self.cmdrecorder is not None:
            self.cmdrecorder.add("!set pad_instrument={0!r}".format(self.pad_instrument))

        self.pad_chords = parse_chords(self.config[what].get("pad_chords", "1"), self.scale, self.key_note)
        self.pad_chord_seq = parse_sequence(self.config[what].get("pad_sequence", "I"), self.pad_chords)
        self.active_preset=what

    def set_lead_note(self, note = None): 
        if self.lead_note is not None:
            self.player.feed_midi(Message('note_off', note=self.lead_note, channel=LEAD_CHANNEL, time=self.message_time))
            self.message_time = 0
        if note is not None:
            self.player.feed_midi(Message('note_on', note=note, channel=LEAD_CHANNEL, time=self.message_time))
        else:
            self.player.feed_other("rest", channel=LEAD_CHANNEL)
        self.lead_note=note
        if self.ui is not None:
            if note is None:
                self.ui.puts("r ")
            else:
                self.ui.puts("{}".format(getLyForMidiNote(note)))

    def do_panic(self):
        self.ui.puts("\nPANIC ")
        note_set = []
        for channel in range(0,16):
            for note in range(0,128):
                note_set.append(Message('note_off', note=note, channel=channel, time=self.message_time)) 
        self.player.feed_midi(*note_set, time=self.message_time, abbr="panic")
        self.message_time = 0

    def set_pad_note(self, note = None): 
        if isinstance(self.pad_note, int):
            self.player.feed_midi(Message('note_off', note=self.pad_note, channel=PAD_CHANNEL, time=self.message_time))
            self.message_time = 0
        elif hasattr(self.pad_note,"__iter__"):
            note_set = []
            for pn in self.pad_note:
                note_set.append(Message('note_off', note=pn, channel=PAD_CHANNEL))
            self.player.feed_midi(*note_set, time=self.message_time, abbr="chord_off")
            self.message_time = 0

        if isinstance(note, int):
            self.player.feed_midi(Message('note_on', note=note, channel=PAD_CHANNEL, time=self.message_time))
        elif hasattr(note,"__iter__"):
            note_set = []
            for pn in note:
                note_set.append(Message('note_on', note=pn, channel=PAD_CHANNEL))
            self.player.feed_midi(*note_set, time=self.message_time, abbr="chord_on")
            self.message_time = 0
        elif note is None:
            self.player.feed_other("rest", channel=LEAD_CHANNEL)

        self.pad_note=note

    def do_note_blip(self, what):
        self.set_lead_note(self.lead_note)

    def do_note(self, what):
        note = calculate_note(what, key_note=self.key_note, scale=self.scale)
        if note is not None:
            self.set_lead_note(note)

    def do_silence(self, what):
        self.set_lead_note()
        self.message_time = 0
        self.set_pad_note()
        self.player.sync_comment("silence all voices")

    def do_rest(self, what):
        self.set_lead_note()

    def do_note_key(self, what):
        global key_note
        self.set_lead_note(self.key_note)

    def do_mark_good(self, what):
        self.set_lead_note()
        self.message_time = 0
        self.set_pad_note()
        # marks MIDI stream (quite crappy/poorly supported)
        self.do_preset(self.active_preset)

    def do_mark_bad(self, what):
        self.set_lead_note()
        self.message_time = 0
        self.set_pad_note()
        # marks MIDI stream (quite crappy/poorly supported)
        self.do_preset(self.active_preset)

    def do_next(self, what):
        self.do_mark_good(what)
        self.do_chord_next(what)

action_mapping = {
"quit": Commands.do_nothing, # handled in the loop
"note_blip": Commands.do_note_blip,
"preset_0": Commands.do_preset,
"preset_1": Commands.do_preset,
"preset_2": Commands.do_preset,
"preset_3": Commands.do_preset,
"preset_4": Commands.do_preset,
"preset_5": Commands.do_preset,
"preset_6": Commands.do_preset,
"preset_7": Commands.do_preset,
"preset_8": Commands.do_preset,
"preset_9": Commands.do_preset,
"mark_bad": Commands.do_mark_bad,
"mark_good": Commands.do_mark_good,
"note_steps-12": Commands.do_note,
"note_steps-11": Commands.do_note,
"note_steps-10": Commands.do_note,
"note_steps-9": Commands.do_note,
"note_steps-8": Commands.do_note,
"note_steps-7": Commands.do_note,
"note_steps-6": Commands.do_note,
"note_steps-5": Commands.do_note,
"note_steps-4": Commands.do_note,
"note_steps-3": Commands.do_note,
"chord_prev": Commands.do_chord_prev,
"chord_next": Commands.do_chord_next,
"chord_repeat": Commands.do_chord_repeat,

"note_steps-2": Commands.do_note,
"note_steps-1": Commands.do_note,
"note_key": Commands.do_note_key,
"note_steps+1": Commands.do_note,
"note_steps+2": Commands.do_note,
"note_steps+3": Commands.do_note,
"note_steps+4": Commands.do_note,
"note_steps+5": Commands.do_note,
"note_steps+6": Commands.do_note,

"next": Commands.do_next,

"note_steps+7": Commands.do_note,
"note_steps+8": Commands.do_note,
"note_steps+9": Commands.do_note,
"note_steps+10": Commands.do_note,
"note_steps+11": Commands.do_note,
"note_steps+12": Commands.do_note,
# "chord_3": Commands.do_chord_3,
# "chord_2": Commands.do_chord_2,
# "chord_1": Commands.do_chord_1,
# "chord_0": Commands.do_chord_0, 
"rest": Commands.do_rest,
"silence": Commands.do_silence,
}






#def find_chord(offset, t = ""):
#    ret = []
#    for step in chordSteps[t]:
#        ret.append(KEY_STEPS[(offset + step) % OCTAVE_STEPS])
#    return ret

_interval_conversion = {
    "b1": -1,
    "\N{music flat sign}}1": -1,
    "1": 0,
    "P1": 0,
    "d2": 0,
    "\N{music natural sign}1": 0,
    "#1": 1,
    "\N{music sharp sign}1": 1,
    "b2": 1,
    "m2": 1,
    "A1": 1,
    "S": 1,
    "\N{music flat sign}2": 1,
    "2": 2,
    "M2": 2,
    "d3": 2,
    "T": 2,
    "\N{music natural sign}2": 2,
    "#2": 3,
    "\N{music sharp sign}2": 3,
    "b3": 3,
    "m3": 3,
    "A2": 3,
    "\N{music flat sign}3": 3,
    "3": 4,
    "M3": 4,
    "d4": 4,
    "\N{music natural sign}3": 4,
    "b4": 4,
    "\N{music flat sign}4": 4,
    "#3": 5,
    "\N{music sharp sign}3": 5,
    "4": 5,
    "P4": 5,
    "A3": 5,
    "\N{music natural sign}4": 5,
    "#4": 6,
    "\N{music sharp sign}4": 6,
    "b5": 6,
    "d5": 6,
    "A4": 6,
    "TT": 6,
    "\N{music flat sign}5": 6,
    "5": 7,
    "P5": 7,
    "d6": 7,
    "\N{music natural sign}5": 7,
    "#5": 8,
    "\N{music sharp sign}5": 8,
    "b6": 8,
    "m6": 8,
    "A5": 8,
    "\N{music flat sign}6": 8,
    "6": 9,
    "M6": 9,
    "d7": 9,
    "\N{music natural sign}6": 9,
    "#6": 10,
    "\N{music sharp sign}6": 10,
    "b7": 10,
    "m7": 10,
    "A6": 10,
    "\N{music flat sign}7": 10,
    "7": 11,
    "M7": 11,
    "d8": 11,
    "\N{music natural sign}7": 11,
    "#7": 12,
    "8": 12,
    "P8": 12,
    "A7": 12,
    "\N{music sharp sign}7": 12,
}

def parse_scale(scale): 
    global _interval_conversion
    if scale is None or scale == "chromatic:":
        return list(range(0,12))
    ret = []
    if scale.startswith("abs:"):
        for s in scale[4:].split():
            if s != "":
                ret.append(int(s))
    elif scale.startswith("rel:"):
        for s in scale[4:].split():
            if s != "":
                if s not in _interval_conversion:
                    raise ConfigError(
                        "unknown relative note {} in {}".format(s, scale))
                ret.append(_interval_conversion[s])
        return ret
    else:
        raise ConfigError("unknown scale: {}".format(scale))

def calculate_note(what, key_note = 60,
        scale=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]): 
    s = what.partition("note_steps")
    if len(s[0]) == 0:
        n = int(s[2])
        octave = n // len(scale) * OCTAVE_STEPS
        offset = n % len(scale)
        note = key_note + octave + scale[offset]
        return note
    return None


def parse_sequence(pad_sequence, chord_map):
    ret = []
    seq = pad_sequence.split("-")
    # pad_sequence = I-vi-IV-V
    for s in seq:
        if s in chord_map:
            ret.append(chord_map[s])
        else:
            raise ConfigError("Unrecognized chord: {}".format(s))
    return ret

_roman = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii",
"xiii", "xiv", "xv", "xvi", "xvii", "xviii", "xix", "xx", "xxi", "xxii", "xxiii", "xxiv"]

def add_for_scale(box, suffix, notes, scale, key_note):
    global _interval_conversion
    global _roman
    n = 0
    for s in scale:
        chord = []
        note = key_note + s
        for o in notes.split():
            if o == "":
                continue
            ival = _interval_conversion.get(o)
            if ival is None:
                raise ConfigError("Unknown interval: " + o)
            chord.append(note + ival)
        box[str(n + 1) + suffix] = chord
        box[_roman[n] + suffix] = chord
        box[_roman[n].upper() + suffix] = chord
        n += 1
    while n < 24:
        box[str(n + 1) + suffix] = []
        box[_roman[n] + suffix] = []
        box[_roman[n].upper() + suffix] = []
        n += 1
    return box

def index_for_note_offset(value):
    global _roman
    value = value.lower()
    if value.isdigit():
        return int(value) - 1
    return _roman.index(value)

def add_override(box, stompers, notes, scale, key_note):
    global _interval_conversion
    global _roman
    for stomp in stompers:
        spl = stomp.partition(":")
        if len(spl[-1]) == 0:
            n = index_for_note_offset(spl[0])
        else:
            n = index_for_note_offset(spl[-1])
        chord = []
        note = key_note + scale[n]
        for o in notes.split():
            if o == "":
                continue
            ival = _interval_conversion.get(o)
            if ival is None:
                raise ConfigError("Unknown interval: " + o)
            chord.append(note + ival)
        box[stomp] = chord

def parse_chords(pad_chords, scale, key_note):
    ret = {}
    for ch in pad_chords.strip().split('>'):
        div = ch.strip().partition("<")
        if len(div[-1]) == 0:
            continue
        if len(div[0]) == 0:
            add_for_scale(ret, div[0], div[-1], scale=scale, key_note=key_note)
        elif div[0][0] == ':':
            add_for_scale(ret, div[0], div[-1], scale=scale, key_note=key_note)
        elif div[0][0] == '(':
            add_override(ret, div[0][1:-1].split(), div[-1], scale=scale, key_note=key_note)
    # pad_chords = <1 3 5> :m<1 m3 5> :7<1 3 5 7> (i iv v)<1 m3 5>

    return ret

