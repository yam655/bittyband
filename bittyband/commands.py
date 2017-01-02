#!/usr/bin/env python3

__all__ = ["Commands"]

import sys
from mido import Message

from .config import ConfigError

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

    def __init__(self, config, player):
        self.config = config
        self.player = player

    def execute(self, cmd, ui=None):
        global action_mapping
        self.ui = ui
        action = action_mapping.get(cmd)
        if action is not None:
            action(self, cmd)

    def do_nothing(self, what):
        pass

    def do_preset(self, what):
        global LEAD_CHANNEL
        global PAD_CHANNEL
        if "key" in self.config[what]:
            self.key_note = int(self.config[what]["key"])
        if "scale" in self.config[what]:
            self.scale = parse_scale(self.config[what]["scale"].strip())
        if "lead_instrument" in self.config[what]:
            self.player.feed_midi(Message('program_change', channel=LEAD_CHANNEL,
                            program=int(self.config[what]["lead_instrument"])))
        if "pad_instrument" in self.config[what]:
            self.player.feed_midi(Message('program_change', channel=PAD_CHANNEL,
                            program=int(self.config[what]["pad_instrument"])))
        active_preset=what
        if self.ui is not None:
            self.ui.puts("Preset Setting to " + what)

    def set_lead_note(self, note = None): 
        if self.lead_note is not None:
            self.player.feed_midi(Message('note_off', note=self.lead_note, channel=LEAD_CHANNEL))
        if note is not None:
            self.player.feed_midi(Message('note_on', note=note, channel=LEAD_CHANNEL))
        self.lead_note=note
        if self.ui is not None:
            self.ui.puts("Note: {}".format(note))

    def do_panic(self):
        for channel in range(0,16):
            for note in range(0,128):
                self.player.feed_midi(Message('note_off', note=note, channel=channel))

    def set_pad_note(self, note = None): 
        if self.pad_note is not None:
            self.player.feed_midi(Message('note_off', note=self.pad_note, channel=PAD_CHANNEL))
        if note is not None:
            self.player.feed_midi(Message('note_on', note=note, channel=PAD_CHANNEL))
        self.pad_note=note

    def do_note_blip(self, what):
        self.set_lead_note(self.lead_note)

    def do_note(self, what):
        note = calculate_note(what, key_note=self.key_note, scale=self.scale)
        if note is not None:
            self.set_lead_note(note)

    def do_silence(self, what):
        self.set_lead_note()
        self.set_pad_note()

    def do_rest(self, what):
        self.set_lead_note()

    def do_note_key(self, what):
        global key_note
        self.set_lead_note(self.key_note)

    def do_mark_good(self, what):
        self.set_lead_note()
        self.set_pad_note()
        # marks MIDI stream (quite crappy/poorly supported)
        self.do_preset(self.active_preset)

    def do_mark_bad(self, what):
        self.set_lead_note()
        self.set_pad_note()
        # marks MIDI stream (quite crappy/poorly supported)
        self.do_preset(self.active_preset)

    def do_next(self, what):
        self.do_mark_good(what)
        # self.do_chord_next(what)

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
# "chord_prev": Commands.do_chord_prev,
# "chord_next": Commands.do_chord_next,
# "chord_repeat": Commands.do_chord_repeat,

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

_rel_scale_conversion = {
    "b1": -1,
    "\N{music flat sign}}1": -1,
    "1": 0,
    "\N{music natural sign}1": 0,
    "#1": 1,
    "\N{music sharp sign}1": 1,
    "b2": 1,
    "\N{music flat sign}2": 1,
    "2": 2,
    "\N{music natural sign}2": 2,
    "#2": 3,
    "\N{music sharp sign}2": 3,
    "b3": 3,
    "\N{music flat sign}3": 3,
    "3": 4,
    "\N{music natural sign}3": 4,
    "b4": 4,
    "\N{music flat sign}4": 4,
    "#3": 5,
    "\N{music sharp sign}3": 5,
    "4": 5,
    "\N{music natural sign}4": 5,
    "#4": 6,
    "\N{music sharp sign}4": 6,
    "b5": 6,
    "\N{music flat sign}5": 6,
    "5": 7,
    "\N{music natural sign}5": 7,
    "#5": 8,
    "\N{music sharp sign}5": 8,
    "b6": 8,
    "\N{music flat sign}6": 8,
    "6": 9,
    "\N{music natural sign}6": 9,
    "#6": 10,
    "\N{music sharp sign}6": 10,
    "b7": 10,
    "\N{music flat sign}7": 10,
    "7": 11,
    "\N{music natural sign}7": 11,
    "#7": 12,
    "\N{music sharp sign}7": 12,
}

def parse_scale(scale): 
    global _rel_scale_conversion
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
                if s not in _rel_scale_conversion:
                    raise ConfigError(
                        "unknown relative note {} in {}".format(s, scale))
                ret.append(_rel_scale_conversion[s])
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

