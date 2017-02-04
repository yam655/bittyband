#!/usr/bin/env python3

__all__ = ["Commands", "LEAD_CHANNEL", "PAD_CHANNEL"]

import sys
from mido import Message, bpm2tempo

from .midinames import getLyForMidiNote
import time
from .utils.cmdutils import *

import locale

locale.setlocale(locale.LC_ALL, '')
code = locale.getpreferredencoding()

LEAD_CHANNEL = 0
PAD_CHANNEL = 1
DRUM_CHANNEL = 9

PAD_VELOCITY = 64


class Commands:

    def __init__(self, config):
        self.config = config
        self.lead_chords = [0, 2, 4]
        self.pad_chords = [0, 2, 4]
        self.pad_chord_idx = -1
        self.pad_chord_seq = []
        self.scale = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
        self.active_preset = None
        self.lead_note = None
        self.pad_note = None
        self.key_note = 60
        self.pad_instrument = 0
        self.lead_instrument = 0
        self.ui = None
        self.message_time = 0
        self.background_on = False

    def wire(self, *, push_player, push_recorder=None, ui=None, metronome, **kwargs):
        self.player = push_player
        self.cmdrecorder = push_recorder
        self.background = metronome
        self.ui = ui

    def execute(self, cmd):
        global action_mapping
        action = action_mapping.get(cmd)
        if action is not None:
            action(self, cmd)

    def play(self, material, realtime=True):
        global action_mapping
        orig_ui = self.ui
        try:
            self.ui = None
            start = None
            end = None
            for line in material:
                if line[0] in "# \t":
                    continue
                p = line.split(",", 1)
                cmd = p[-1]
                end = float(p[0])
                if start is not None:
                    s = (end - start)
                    if s > 0:
                        #                   self.message_time = int(s * 1000000)
                        self.message_time = int(s * 1000)
                        if realtime:
                            time.sleep(s)
                if cmd[0] == "!":
                    continue
                sys.stderr.write(cmd + "\n\r")
                action = action_mapping.get(cmd)
                if action is not None:
                    action(self, cmd)
                start = end
            self.do_silence("silence")
        finally:
            self.ui = orig_ui

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

    def do_preset(self, what, *, note_it = False):
        global LEAD_CHANNEL
        global PAD_CHANNEL
        if what is None:
            return

        if what != self.active_preset:
            self.pad_chord_idx = -1
            self.pad_chord_seq = []
        title = self.config[what]["title"]
        midi_set = []
        if self.cmdrecorder is not None and note_it:
            self.cmdrecorder.add(what)
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
            self.pad_instrument = int(self.config[what]["pad_instrument"])
        else:
            self.pad_instrument = 0
        self.player.feed_midi(Message('program_change', channel=PAD_CHANNEL,
                                      program=self.pad_instrument, time=0))
        if self.cmdrecorder is not None:
            self.cmdrecorder.add("!set pad_instrument={0!r}".format(self.pad_instrument))

        self.pad_chords = parse_chords(self.config[what].get("pad_chords", "1"), self.scale, self.key_note)
        self.pad_chord_seq = parse_sequence(self.config[what].get("pad_sequence", "I"), self.pad_chords)
        self.active_preset = what
        bpm = 120
        if "bpm" in self.config[what]:
            bpm = self.config[what].getint("bpm")
        timing = "common"
        if "timing" in self.config[what]:
            timing = self.config[what]["timing"]
        timing = parse_timing(timing)
        if timing is None:
            self.background.set_tempo(None, None, bpm2tempo(bpm))
        else:
            nude = timing.partition("/")
            self.background.set_tempo(int(nude[0]), int(nude[-1]), bpm2tempo(bpm))

    def set_lead_note(self, note=None):
        if self.lead_note is not None:
            self.player.feed_midi(
                Message('note_off', note=self.lead_note, channel=LEAD_CHANNEL, time=self.message_time))
            self.message_time = 0
        if note is not None:
            self.player.feed_midi(Message('note_on', note=note, channel=LEAD_CHANNEL, time=self.message_time))
        else:
            self.player.feed_other("rest", channel=LEAD_CHANNEL)
        self.lead_note = note
        if self.ui is not None:
            if note is None:
                self.ui.puts("r ")
            else:
                self.ui.puts("{} ".format(getLyForMidiNote(note)))

    def do_panic(self):
        if self.ui is not None:
            self.ui.puts("\nPANIC ")
        note_set = []
        for channel in range(0, 16):
            for note in range(0, 128):
                note_set.append(Message('note_off', note=note, channel=channel, time=self.message_time))
        self.player.feed_midi(*note_set, time=self.message_time, abbr="panic")
        self.message_time = 0

    def set_pad_note(self, note=None):
        global PAD_VELOCITY
        if isinstance(self.pad_note, int):
            self.player.feed_midi(Message('note_off', note=self.pad_note, channel=PAD_CHANNEL, time=self.message_time))
            self.message_time = 0
        elif hasattr(self.pad_note, "__iter__"):
            note_set = []
            for pn in self.pad_note:
                note_set.append(Message('note_off', note=pn, channel=PAD_CHANNEL))
            self.player.feed_midi(*note_set, time=self.message_time, abbr="chord_off")
            self.message_time = 0

        if isinstance(note, int):
            self.player.feed_midi(
                Message('note_on', note=note, channel=PAD_CHANNEL, time=self.message_time, velocity=PAD_VELOCITY))
            if self.ui is not None:
                self.ui.puts("< {} > ".format(getLyForMidiNote(note)))
        elif hasattr(note, "__iter__"):
            note_set = []
            if self.ui is not None:
                self.ui.puts("< ")
            for pn in note:
                note_set.append(Message('note_on', note=pn, channel=PAD_CHANNEL, velocity=PAD_VELOCITY))
                if self.ui is not None:
                    self.ui.puts("{} ".format(getLyForMidiNote(pn)))
            if self.ui is not None:
                self.ui.puts("> ")
            self.player.feed_midi(*note_set, time=self.message_time, abbr="chord_on")
            self.message_time = 0
        elif note is None:
            self.player.feed_other("rest", channel=LEAD_CHANNEL)
        self.pad_note = note

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
        self.do_preset(self.active_preset, note_it=True)

    def do_mark_bad(self, what):
        self.set_lead_note()
        self.message_time = 0
        self.set_pad_note()
        # marks MIDI stream (quite crappy/poorly supported)
        self.do_preset(self.active_preset, note_it=True)

    def do_next(self, what):
        self.do_mark_good(what)
        self.do_chord_next(what)

    def do_octave(self, name):
        global OCTAVE_STEPS
        if name == "octave_up":
            self.key_note += OCTAVE_STEPS
        elif name == "octave_down":
            self.key_note -= OCTAVE_STEPS

    def do_play_pause(self, name):
        if self.background_on:
            self.set_lead_note()
            self.set_pad_note()
            self.background.pause()
            self.background_on = False
        else:
            self.background.play()
            self.background_on = True

    def do_rewind(self, name):
        self.background.rewind()
        self.background.pause()
        self.set_lead_note()
        self.set_pad_note()
        self.pad_chord_idx = -1

    def do_menu(self, name):
        pass


action_mapping = {
    "quit": Commands.do_nothing,  # handled in the loop
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
    "rest": Commands.do_rest,
    "silence": Commands.do_silence,

    "octave_up": Commands.do_octave,
    "octave_down": Commands.do_octave,
    "play_pause": Commands.do_play_pause,
    "rewind": Commands.do_rewind,
    "menu": Commands.do_menu,
}



