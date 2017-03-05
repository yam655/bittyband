#!/usr/bin/env python3

import numpy
import aubio

from ..midinames import getLyForMidiNote

HOP_SIZE = 256

chordies = {
    {"c", "e", "g"}: 'c',

}

def nameForLimitedNote(note):
    return getLyForMidiNote(note + 60)

class Automate:
    def __init__(self):
        pass

    def process(self, beat_box):
        source = aubio.source(beat_box.bits["media"], 0, HOP_SIZE)

        # Total number of frames read
        total_frames = 0
        samplerate = source.samplerate
        tempoer = aubio.tempo("specdiff", HOP_SIZE * 2, HOP_SIZE, samplerate)
        # List of beats, in samples
        beats = []
        notes_o = aubio.notes("default", HOP_SIZE * 2, HOP_SIZE, samplerate)
        # notes_o.set_tolerance(0.7)
        # ignore frames under this level (dB)
        notes_o.set_silence(-60)
        last_beat = beat_box.new_beat(0.0)

        while True:
            samples, read = source()

            is_beat = tempoer(samples)
            location = total_frames / float(samplerate)
            if is_beat:
                this_beat = tempoer.get_last_s()
                last_beat["beat"] = this_beat
                last_beat["end-loc"] = location
                last_beat = beat_box.new_beat(location)
                beats.append(this_beat)

            new_note = notes_o(samples)
            beat_box.add_note(location, *new_note)
            last_beat["notes"].append(location)

            if read < HOP_SIZE:
                last_beat["end-loc"] = location
            total_frames += read
            if read < HOP_SIZE: break

        if len(beat_box.notes) > 0 and beat_box.notes[-1]["midi"] != 0:
            end_loc = total_frames / float(samplerate)
            if beat_box.notes[-1]["location"] == end_loc:
                beat_box.notes[-1]["midi"] = 0
            else:
                beat_box.add_note(end_loc, 0, 0, beat_box.notes[-1]["midi"])
        prev_beat = None
        for beat in beat_box.beats:
            self.elaborate_beat(beat, prev_beat, beat_box)
            prev_beat = beat

        # # Convert to periods and to bpm
        # bpm = ""
        # if len(beats) > 1:
        #     if len(beats) >= 4:
        #         bpms = 60. / numpy.diff(beats)
        #         bpm = numpy.median(bpms)
        # importer.metadata["audio"]["bpm"] = str(bpm)
        # importer.changed = True

    def elaborate_beat(self, beat, old_beat, beat_box):
        start = beat["start-loc"]
        end = beat["end-lock"]
        note_lengths = {}
        block_lengths = {}
        for noteloc in beat["notes"]:
            note = beat_box.note[noteloc]
            if note["midi"] == 0:
                continue
            n = note % 12
            o = note // 12
            d = beat_box.note[noteloc+1]["location"] - note["location"]
            if n not in note_lengths:
                note_lengths[n] = d
            else:
                note_lengths[n] += d
            if o not in block_lengths:
                block_lengths[o] = d
            else:
                block_lengths[d] += d
        top = []
        dropkeys = []
        for k, v in note_lengths.items():
            if v < (end - start) / 10:
                dropkeys.append(k)
                continue
            for i in range(len(top)):
                if v > top[i][1]:
                    top.insert(i, (k, v))
                    break
            else:
                top.append((k, v))
        for k in dropkeys:
            del note_lengths[k]
        beat["important-notes"] = top
        beat["chord"] = top[0:3]
