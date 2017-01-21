#!/usr/bin/env python3

from ..errors import ConfigError

OCTAVE_STEPS = 12

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
        return list(range(0, 12))
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


def calculate_note(what, key_note=60,
                   scale=(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11)):
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

def parse_timing(timing):
    if timing == "common":
        timing = "4/4"
    elif timing == "waltz":
        timing = "3/4"
    elif timing == "ballad":
        timing = "2/4"
    elif timing == "cut":
        timing = "2/2"
    elif timing == "uncommon":
        timing = None
    elif "/" not in timing:
        raise ConfigError("Unknown timing: " + timing)
    return timing

