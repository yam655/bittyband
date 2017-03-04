#!/usr/bin/env python3

import numpy
import aubio

HOP_SIZE = 1024


class Automate:
    def __init__(self):
        pass

    def process(self, importer):
        source = aubio.source(importer.bits["media"], 0, HOP_SIZE)

        # Total number of frames read
        total_frames = 0
        samplerate = source.samplerate
        tempoer = aubio.tempo("specdiff", HOP_SIZE * 2, HOP_SIZE, samplerate)
        # List of beats, in samples
        beats = []
        notes_o = aubio.notes("default", HOP_SIZE * 2, HOP_SIZE, samplerate)
        # ignore frames under this level (dB)
        notes_o.set_silence(-40)
        popularity = {}
        last_rest = False

        while True:  # reading loop
            samples, read = source()
            mark = ""

            is_beat = tempoer(samples)
            if is_beat:
                this_beat = tempoer.get_last_s()
                mark = "- beat"
                beats.append(this_beat)

            new_note = notes_o(samples)

            location = total_frames / float(samplerate)
            if (new_note[0] != 0):
                last_rest = False
                midi_note = int(new_note[0])
                if midi_note >= 96:
                    midi_note = ""
                else:
                    popularity.setdefault(midi_note % 12, 0)
                    popularity[midi_note % 12] += 1
                if location in importer.data:
                    importer.data[location]["note"] = midi_note
                    if mark:
                        importer.data[location]["mark"] = mark
                else:
                    importer.add_row(location, mark=mark, note=midi_note)
            elif new_note[2] != 0:
                if location in importer.data:
                    importer.data[location]["note"] = ""
                    if mark:
                        importer.data[location]["mark"] = mark
                    last_rest = True
                elif not last_rest:
                    importer.add_row(location, mark=mark, note="")
                    last_rest = True

            total_frames += read
            if read < HOP_SIZE: break

        popnotes = []
        noteNames = ["c", "cis", "d", 'dis', "e", "f", "fis", "g", "gis", "a", "ais", "b"]
        for n in range(0,12):
            popnotes.append((noteNames[n], popularity.get(n, 0)))
        importer.metadata["audio"]["popular-notes"] = repr(popnotes)

        # Convert to periods and to bpm
        bpm = ""
        if len(beats) > 1:
            if len(beats) >= 4:
                bpms = 60. / numpy.diff(beats)
                bpm = numpy.median(bpms)
        importer.metadata["audio"]["bpm"] = str(bpm)
        importer.changed = True
