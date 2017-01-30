#!/usr/bin/env

import csv
from pathlib import Path
from configparser import ConfigParser

import mido
import pyglet
from mido import Message

from ..midinames import getLyForMidiNote
from .csvplayer import CsvPlayer
from ..utils.cmdutils import *
from ..utils.time import human_duration, from_human_duration, filename_iso_time
from .importcsvdialect import ImportCsvDialect
from ..exportly import ExportLy
from ..exportmidi import ExportMidi
from ..exporttxt import ExportTxt
from ..commands import LEAD_CHANNEL, PAD_CHANNEL


class Importer:
    def __init__(self, config):
        self.config = config
        self.ui = None
        self.data = {}
        self.order = []
        self.player = None
        self.start_segment = None
        self.start_line = 0
        self.end_segment = None
        self.song_data = {}
        self.last_note = None
        self.playing_row = None
        self.project_dir = Path(config["instance"]["project_dir"])
        self.changed = False
        self.last_bpm_tap = ""

    def wire(self, *, ui, import_lister, csv_player, push_player, **kwargs):
        self.ui = ui
        self.import_lister = import_lister
        self.csv_player = csv_player
        self.push_player = push_player

    def _play_live_seek(self, seconds):
        if seconds < 0 and self.player.time + seconds >= 0:
            self.player.seek(self.player.time + seconds)
            self.player.play()
            return

        if self.play_length is None:
            return

        offset = seconds + self.player.time
        while offset < 0:
            offset += self.play_length
        while offset > self.play_length:
            offset -= self.play_length
        self.player.seek(offset)
        self.player.play()

    def _start_player(self):
        media = self.bits["media"]
        self.play_length = self.bits["length_secs"]
        sound = pyglet.media.load(str(media))
        group = pyglet.media.SourceGroup(sound.audio_format, sound.video_format)
        group.loop = True
        group.queue(sound)
        self.player = pyglet.media.Player()
        self.player.queue(group)

    def _do_play(self, line):
        self.start_segment = self.order[line]
        self.start_line = line
        self.end_segment = None
        self.playing_row = None
        if self.player.playing:
            self.csv_player.pause()
            self.csv_player.silence()
            self.player.pause()
        else:
            self.player.seek(self.start_segment)
            self.player.play()
            self.csv_player.silence()
            self.csv_player.seek(self.start_line)
            self.csv_player.play()

    def _do_play_chords(self, line):
        self.start_segment = self.order[line]
        self.start_line = line
        self.end_segment = None
        self.playing_row = None
        if self.csv_player.playing:
            self.csv_player.pause()
            self.player.pause()
            self.csv_player.silence()
        else:
            self.csv_player.silence()
            self.player.pause()
            self.csv_player.seek(self.start_line)
            self.csv_player.play()

    def _do_play_segment(self, *, line, advertise=True):
        if line == len(self.order) - 1:
            self.spreader.show_status("Can not play last segment")
            self.playing_row = None
            return False
        self.start_segment = self.order[line]
        self.start_line = line
        self.playing_row = line
        self.end_segment = self.order[line + 1]
        if advertise:
            self.spreader.show_status("Playing current line".format(human_duration(self.start_segment), human_duration(self.end_segment)))
        self.player.seek(self.start_segment)
        self.player.play()
        self.csv_player.seek(self.start_line)
        self.csv_player.play()

    def _do_repeat_mark(self, *, line):
        datum = self.data.get(self.order[line])
        if datum.get("mark_idx", -1) < 0:
            self.spreader.show_status("This line isn't in a marked section")
            return False
        self.playing_row = None
        self.start_line = datum["mark_idx"]
        end_line = self.start_line
        while end_line < len(self.order) and self.data.get(self.order[end_line]).get("mark_idx",-1) == self.start_line:
            end_line += 1
        if end_line >= len(self.order):
            end_line = len(self.order) - 1

        start_secs = self.order[line]
        self.start_segment = start_secs
        self.end_segment = self.order[end_line]
        starting_at = ""
        if line != self.start_line:
            starting_at = " starting at {}".format(human_duration(start_secs))
        self.spreader.show_status("Playing: {} to {}{}".format(human_duration(self.start_segment), human_duration(self.end_segment), starting_at))
        self.player.seek(self.start_segment)
        self.player.play()
        self.player.seek(self.start_segment)
        self.player.play()
        self.csv_player.seek(self.start_line)
        self.csv_player.play()

    def _do_delete(self, *, line):
        if line == 0 or line == len(self.order) - 1:
            self.spreader.show_status("Can't delete top or bottom")
            return False
        item = self.order[line]
        del self.data[item]
        del self.order[line]
        self.spreader.invalidate = True
        self.changed = True
        return True

    def _do_idle(self):
        if not self.player:
            self.spreader.show_status(self.bits["title"])
            self._start_player()
        t = self.player.time
        if self.player.playing and self.end_segment is not None and t >= self.end_segment:
            self.player.seek(self.start_segment)
            self.csv_player.seek(self.start_line)
            self.player.play()
            self.csv_player.play()
        # display = human_duration(t, floor=True)
        # self.spreader.display_time(display)
        # display = human_duration(self.order[self.csv_player.line-1], floor=1)
        # self.spreader.display_line(display)
        row = self.playing_row
        if row is not None and row != self.spreader.active:
            self._do_play_segment(line=self.spreader.active, advertise=False)
        if not self.player.playing:
            if len(self.order) != len(self.data):
                self.update_order()
                self._propagate()
                self.spreader.refresh()
            elif self._need_propagate:
                self._propagate()
                self.spreader.refresh()

    def _do_tap(self, *, line):
        offset = self.player.time
        if offset not in self.data:
            self.add_row(offset)
        self.spreader.show_status(human_duration(offset, 3))
        self.changed = True
        return False

    def _do_beat_repeat(self, bpm, *, line):
        if line < 0 or bpm is None:
            return self.last_bpm_tap
        self.last_bpm_tap = bpm
        i = 0
        while i < len(bpm) and bpm[i].isnumeric():
            i += 1
        end = i
        while i < len(bpm) and bpm[i].isspace():
            i += 1
        if i >= len(bpm):
            self.spreader.show_status("Unrecognized rate: " + bpm)
            return True

        try:
            rep = int(bpm[:end])
        except ValueError:
            self.spreader.show_status("Illegal rate: " + bpm)
            return True

        if bpm[i] in "Xx/@":
            i += 1
        check = self.parse_timecode(timecode = bpm[i:], line = line)
        if check is None:
            self.spreader.show_status("Problem parsing rate: " + bpm)
            return True
        offset = check - self.order[line]
        location = self.order[line]
        bottom = self.order[-1]
        x = 0
        while x < rep:
            location += offset
            if location < 0.0 or location > bottom:
                break
            if location not in self.data:
                self.add_row(location)
            x += 1
        self.spreader.show_status("{} rows added every {}".format(x, human_duration(offset, 3)))
        self.changed = True
        return False

    _track_change_states = ["", "crap", "resume", "unknown", "track"]

    def _do_track(self, *, line):
        datum = self.data[self.order[line]]
        got = datum.get("track-change","")
        if got == "":
            last = ""
            for i in range(line - 1, -1, -1):
                d = self.data[self.order[line]]
                last = d.get("track-change", "")
                if last != "":
                    got = last
                    break

        idx = self._track_change_states.index(got)
        idx += 1
        if idx >= len(self._track_change_states):
            idx = 0
        datum["track-change"] = self._track_change_states[idx]
        self._need_propagate = True
        self.spreader.refresh_line(line)
        self.changed = True
        return True

    _chord_options = ["", "chord", "rest", "resume"]
    def _do_chord(self, *, line):
        datum = self.data[self.order[line]]
        got = datum.get("chord-change","")
        # if got == "":
        #     for i in range(line - 1, -1, -1):
        #         d = self.data[self.order[i]]
        #         last = d.get("chord-change", "")
        #         if last != "":
        #             break

        idx = self._chord_options.index(got)
        idx += 1
        if idx >= len(self._chord_options):
            idx = 0
        datum["chord-change"] = self._chord_options[idx]
        self._need_propagate = True
        self.spreader.refresh_line(line)
        self.changed = True
        return True

    def _propagate(self):
        self._need_propagate = False
        last_track = "unknown"
        last_chord = "rest"
        self._tracks = []
        chord_idx = -1
        if str(0.0) in self.metadata:
            this_track = self.find_song_data(0.0)
        else:
            this_track = self.find_song_data(-1)
        self.song_data[-1] = this_track
        chord_values = this_track["pad_chord_seq"]
        last_mark = -1
        idx = -1
        for location in self.order:
            idx += 1
            datum = self.data.get(location)
            next_track = datum.get("track-change", "")
            next_chord = datum.get("chord-change", "")
            mark = datum.get("mark","")
            if mark != "":
                if mark[0] not in ".-*@+=: ":
                    last_mark = idx
            datum["mark_idx"] = last_mark
            if next_track == "":
                if last_track == "unknown":
                    datum["track_ui"] = "  ?"
                    datum["track_id"] = -1
                elif last_track == "track":
                    datum["track_id"] = self._tracks[-1]
                    datum["track_ui"] = " {:02d}".format(len(self._tracks))
                elif last_track == "crap":
                    datum["track_ui"] = "  -"
                    datum["track_id"] = -1
            elif next_track == "unknown":
                datum["track_ui"] = "? ?"
                datum["track_id"] = -1
                last_track = next_track
            elif next_track == "track":
                last_track = next_track
                self._tracks.append(datum["location"])
                datum["track_id"] = self._tracks[-1]
                datum["track_ui"] = "*{:02d}".format(len(self._tracks))
                this_track = self.find_song_data(self._tracks[-1])
                self.song_data[self._tracks[-1]] = this_track
                chord_values = this_track["pad_chord_seq"]
            elif next_track == "crap":
                last_track = next_track
                datum["track_ui"] = "- -"
                datum["track_id"] = -1
            elif next_track == "resume":
                if len(self._tracks) == 0:
                    datum["track_ui"] = "/ ?"
                    datum["track_id"] = -1
                    last_track = "unknown"
                else:
                    datum["track_id"] = self._tracks[-1]
                    datum["track_ui"] = "+{:02d}".format(len(self._tracks))
                    last_track = "track"
            if next_chord == "":
                if last_chord == "chord":
                    datum["chord_value"] = None
                    datum["chord_ui"] = " * "
                elif last_chord == "rest":
                    datum["chord_value"] = None
                    datum["chord_ui"] = " : "
            elif next_chord == "chord":
                last_chord = next_chord
                chord_idx += 1
                if chord_idx >= len(chord_values):
                    chord_idx = 0
                datum["chord_value"] = chord_values[chord_idx]
                datum["chord_ui"] = ">*<"
            elif next_chord == "rest":
                last_chord = next_chord
                datum["chord_value"] = tuple()
                datum["chord_ui"] = "-:-".format(len(self._tracks))
            elif next_chord == "resume":
                datum["chord_value"] = chord_values[chord_idx]
                datum["chord_ui"] = "}+{"
                last_chord = "chord"
        self.metadata["audio"]["tracks"] = str(len(self._tracks))
        for t in self._tracks:
            if str(t) not in self.metadata:
                self.metadata.add_section(str(t))
                self.set_defaults_for_song(t)
            if self.data[t].get("mark","") == "":
                self.data[t]["mark"] = "Track @{}".format(human_duration(t,0))
            self.metadata[str(t)]["title"] = self.data[t]["mark"]

    def parse_timecode(self, *, timecode, line):
        if timecode is None or timecode.strip() == "":
            return None
        timecode = timecode.lower().strip()
        if ":" in timecode:
            location = from_human_duration(timecode)
        elif timecode.endswith("beat") or timecode.endswith("beats"):
            if timecode.endswith("beat"):
                timecode = timecode[:-4].strip()
            else:
                timecode = timecode[:-5].strip()
            negate = 1
            if timecode.startswith("-"):
                negate = -1
                timecode = timecode[1:].strip()
            trial = 1
            if len(timecode) > 0:
                try:
                    trial = float(timecode)
                except ValueError:
                    return None
            next = line+1
            if next == len(self.order):
                next -= 1
            offset = self.order[next]  - self.order[line]
            location = self.order[line] + offset * trial * negate

        elif timecode.endswith("bpm") or timecode.endswith("b"):
            if timecode.endswith("b"):
                timecode = timecode[:-1].strip()
            else:
                timecode = timecode[:-3].strip()
            negate = 1
            if timecode.startswith("-"):
                negate = -1
                timecode = timecode[1:]
            if "@" in timecode:
                s = timecode.split("@", 1)
            elif "/" in timecode:
                s = timecode.split("/", 1)
            elif "x" in timecode:
                s = timecode.split("x", 1)
            else:
                s = ["1", timecode]
            try:
                offset = mido.bpm2tempo(int(timecode.strip())) / 1000000 * int(s[0].strip()) * negate

            except ValueError:
                return None
            location = self.order[line] + offset

        else:
            try:
                offset = float(timecode)
            except ValueError:
                return None
            location = self.order[line] + offset
        return location

    def _do_jump(self, timecode, *, line):
        location = self.parse_timecode(timecode=timecode, line=line)
        if location is None:
            self.spreader.show_status("Invalid timecode or offset: {}".format(timecode))
        else:
            self._perform_jump(location)

    def _perform_jump(self, location, callback=None, callback_args={}):
        newline = None
        if location in self.data:
            try:
                newline = self.order.index(location)
            except ValueError:
                self.update_order()
                newline = self.order.index(location)
        if newline is None:
            self.changed = True
            was_p_playing = self.player.playing
            was_c_playing = self.csv_player.playing
            self.add_row(location)
            if was_p_playing:
                self.player.pause()
            if was_c_playing:
                self.csv_player.pause()
            if callback is not None:
                callback(location, **callback_args)
            self._do_idle()
            newline = self.order.index(location)
            self.player.seek(location)
            self.csv_player.seek(newline)
            if was_p_playing:
                self.player.play()
            if was_c_playing:
                self.csv_player.play()
        self.spreader.move_to(newline)

    def _do_lyric(self, lyric, *, line):
        if line < 0 or lyric is None:
            return self.data[self.order[-line]].get("lyric","")
        self.data[self.order[line]]["lyric"] = lyric.strip()
        self.changed = True
        return True

    def _do_line_mark(self, *, line):
        self.changed = True
        lyric = self.data[self.order[line]].get("lyric", "")
        if lyric == "":
            self.data[self.order[line]]["lyric"] = "/"
            return
        if lyric[0] == '/':
            self.data[self.order[line]]["lyric"] = "\\" + self.data[self.order[line]]["lyric"][1:]
        elif lyric[0] == '\\':
            self.data[self.order[line]]["lyric"] = self.data[self.order[line]]["lyric"][1:]
        else:
            self.data[self.order[line]]["lyric"] = "/" + self.data[self.order[line]]["lyric"]
        return True

    def _do_mark(self, mark, *, line):
        if line < 0 or mark is None:
            return self.data[self.order[-line]].get("mark","")
        self.data[self.order[line]]["mark"] = mark
        self.changed = True
        return True

    def _do_clone_up(self, *, line):
        self._do_clone(line, -1)

    def _do_clone_down(self, *, line):
        self._do_clone(line, +1)

    def _do_clone(self, line, dir = 1):
        base = self.order[line]
        if line + 1 == len(self.order):
            return False
        next = self.order[line+dir]
        offset = (next - base) / 2
        if offset < 0.0005 and offset > -0.0005:
            return False
        loc = base + offset
        self._perform_jump(loc, callback=self.clone_goodies, callback_args={"from_loc":base})

    def _do_nudge(self, offset, *, line):
        if line is None or line == "":
            return False
        if line == 0 or line == len(self.order) -1:
            self.spreader.show_status("Can't nudge top or bottom.")
            return False
        try:
            offset = float(offset)
        except ValueError:
            self.spreader.show_status("Invalid offset: {}".format(offset))
            return False
        base = self.order[line]
        location = base + offset
        if line > 0 and self.order[line-1] > location:
            self.spreader.show_status("Invalid offset: {}; can't go over {}".format(offset, self.order[line - 1]))
            return False
        if line < len(self.order) - 1 and self.order[line+1] < location:
            self.spreader.show_status("Invalid offset: {}; can't go under {}".format(offset, self.order[line + 1]))
            return False

        self._perform_jump(location, callback=self.swap_goodies, callback_args={"from_loc": self.order[line]})
        line_now = line
        if offset < 0:
            line_now += 1
        self._do_delete(line=line_now)
        self.spreader.move_to(line+1)
        self._do_idle()
        self.spreader.move_to(line)

    def clone_goodies(self, to_loc, from_loc):
        self.changed = True
        data_from = self.data[from_loc]
        data_to = self.data[to_loc]
        for k in data_from.keys():
            if k == "location":
                continue
            data_to[k] = data_from[k]

    def _do_shift_up(self, *, line):
        self._do_shift(line, -1)

    def _do_shift_down(self, *, line):
        self._do_shift(line, +1)

    def _do_shift(self, line, dir = 1):
        base = self.order[line]
        if line + 1 == len(self.order):
            return
        next = self.order[line+dir]
        offset = (next - base) / 2
        if offset < 0.0005 and offset > -0.0005:
            return
        loc = base + offset
        self._perform_jump(loc, callback=self.swap_goodies, callback_args={"from_loc":base})

    def swap_goodies(self, to_loc, from_loc):
        self.changed = True
        data_from = self.data[from_loc]
        data_to = self.data[to_loc]
        for k in data_from.keys():
            if k == "location":
                continue
            data_to[k], data_from[k] = data_from[k], data_to.get(k,"")

    def _do_export_midi(self, filename, *, line):
        if filename is None or len(filename.strip()) == 0:
            self.export_midi(self.project_dir / "{}.midi".format("export"))
        else:
            self.export_midi(self.project_dir / filename)
        return False

    def _do_export_lily(self, filename, *, line):
        if filename is None or len(filename.strip()) == 0:
            self.export_ly(self.project_dir / "{}.ly".format("export"))
        else:
            self.export_ly(self.project_dir / filename)
        return False

    def _do_export_txt(self, filename, *, line):
        if filename is None or len(filename.strip()) == 0:
            self.export_txt(self.project_dir / "{}.txt".format("export"))
        else:
            self.export_txt(self.project_dir / filename)
        return False

    def export_midi(self, output):
        exporter = ExportMidi(self.config, output)
        csvplayr = CsvPlayer(self.config)
        csvplayr.wire(importer=self, push_player=exporter, realtime=False)
        exporter.start()
        csvplayr.export()
        exporter.end()

    def export_txt(self, output):
        exporter = ExportTxt(self.config, output)
        csvplayr = CsvPlayer(self.config)
        csvplayr.wire(importer=self, push_player=exporter, realtime=False)
        exporter.start()
        csvplayr.export()
        exporter.end()

    def export_ly(self, output):
        exporter = ExportLy(self.config, output)
        csvplayr = CsvPlayer(self.config)
        csvplayr.wire(importer=self, push_player=exporter, realtime=False)
        exporter.start()
        csvplayr.export()
        exporter.end()

    def _do_lead_rest(self, *, line):
        self.changed = True
        datum = self.data[self.order[line]]
        datum["note"] = ""
        datum["note_ui"] = "-"
        return True

    def _do_up_note(self, *, line):
        datum = self.data[self.order[line]]
        track_id = datum.get("track_id", -1)
        got = datum.get("note","")
        if got == "":
            got = self.last_note
            if got == "" or got is None:
                song_stuff = self.song_data.get(track_id)
                got = song_stuff["key_note"]
        else:
            got += 1
            if got >= 128:
                got -= 120
        got = abs(got) % 128
        self.last_note = got
        datum["note"] = got
        datum["note_ui"] = getLyForMidiNote(got)
        self.changed = True
        return True

    def _do_down_note(self, *, line):
        datum = self.data[self.order[line]]
        track_id = datum.get("track_id", -1)
        got = datum.get("note","")
        if got == "":
            got = self.last_note
            if got == "" or got is None:
                song_stuff = self.song_data.get(track_id)
                got = song_stuff["key_note"]
        else:
            got -= 1
            if got < 0:
                got += 120
        got = abs(got) % 128
        self.last_note = got
        datum["note"] = got
        datum["note_ui"] = getLyForMidiNote(got)
        self.changed = True
        return True

    def _do_up_octave(self, *, line):
        datum = self.data[self.order[line]]
        track_id = datum.get("track_id", -1)
        got = datum.get("note","")
        if got == "":
            got = self.last_note
            if got == "" or got is None:
                song_stuff = self.song_data.get(track_id)
                got = song_stuff["key_note"]
        else:
            got += 12
            if got >= 128:
                got -= 120
        got = abs(got) % 128
        self.last_note = got
        datum["note"] = got
        datum["note_ui"] = getLyForMidiNote(got)
        self.changed = True
        return True

    def _do_down_octave(self, *, line):
        datum = self.data[self.order[line]]
        track_id = datum.get("track_id", -1)
        got = datum.get("note","")
        if got == "":
            got = self.last_note
            if got == "" or got is None:
                song_stuff = self.song_data.get(track_id)
                got = song_stuff["key_note"]
        else:
            got -= 12
            if got < 0:
                got += 120
                if got >= 128:
                    got -= 12
        got = abs(got) % 128
        self.last_note = got
        datum["note"] = got
        datum["note_ui"] = getLyForMidiNote(got)
        self.changed = True
        return True

    def _do_up_on_scale(self, *, line):
        datum = self.data[self.order[line]]
        track_id = datum.get("track_id", -1)
        song_stuff = self.song_data.get(track_id)
        if song_stuff is None:
            song_stuff = self.find_song_data(track_id)
        got = datum.get("note","")
        if got == "":
            got = self.last_note
        if got == "" or got is None:
            got = song_stuff["key_note"]

        key_note = song_stuff["key_note"]
        adjusted_for_key = got
        while adjusted_for_key < key_note:
            adjusted_for_key += 12
        while adjusted_for_key >= key_note + 12:
            adjusted_for_key -= 12
        offset_from_key = adjusted_for_key - key_note
        trial = None
        for scale_offset in song_stuff["scale_parsed"]:
            if scale_offset > offset_from_key:
                trial = scale_offset
                break
        if trial is None:
            trial = song_stuff["scale_parsed"][0] + 12
        trial = trial + key_note + got - adjusted_for_key
        if trial < 0:
            trial += 120
        if trial >= 120:
            trial -= 120
        self.last_note = trial
        datum["note"] = trial
        datum["note_ui"] = getLyForMidiNote(trial)
        self.changed = True
        return True

    def _do_down_on_scale(self, *, line):
        datum = self.data[self.order[line]]
        track_id = datum.get("track_id", -1)
        song_stuff = self.song_data.get(track_id)
        if song_stuff is None:
            song_stuff = self.find_song_data(track_id)
        got = datum.get("note","")
        if got == "":
            got = self.last_note
        if got == "" or got is None:
            got = song_stuff["key_note"]

        key_note = song_stuff["key_note"]
        adjusted_for_key = got
        while adjusted_for_key < key_note:
            adjusted_for_key += 12
        while adjusted_for_key >= key_note + 12:
            adjusted_for_key -= 12
        offset_from_key = adjusted_for_key - key_note
        trial = None
        for scale_offset in song_stuff["scale_parsed"][::-1]:
            if scale_offset < offset_from_key:
                trial = scale_offset
                break
        if trial is None:
            trial = song_stuff["scale_parsed"][-1] - 12
        trial = trial + key_note + got - adjusted_for_key
        if trial < 0:
            trial += 120
        if trial >= 120:
            trial -= 120
        self.last_note = trial
        datum["note"] = trial
        datum["note_ui"] = getLyForMidiNote(trial)
        self.changed = True
        return True

    def _do_sample_note(self, *, line):
        datum = self.data[self.order[line]]
        self.csv_player.set_lead_note(datum["note"] )
        self.spreader.show_status("Sampling note...")
        self.ui.get_key(timeout=0.2)
        self.csv_player.set_lead_note(None)
        self.spreader.show_status("Done...")
        return False

    def _do_backup(self, *, line):
        self.backup()
        self.spreader.show_status("Backup complete.")
        return True

    def prepare_keys(self, spreader):
        self.spreader = spreader
        spreader.register_idle(self._do_idle)
        spreader.on_exit(self.save)
        """ Key commands:
            ^J : Go to line and repeat
            ^N : shift down by half
            ^P : shift up by half
            '@' : jump to or create by timecode
            '.' : mark current audio location as a beat
            '"' / 'L' / 'l' : enter lyrics for row
                - Start with '/' for new line.
                - Start with '\\' for new row
            "'" - Take lead note up an octave
            "," - take lead note down an octave
            "]" - shift note up one by scale
            "[" - shift note down one by scale
            "}" - shift note up by one half-tone
            "{" - shift note down by one half-tone
            "/" : change the line separator indicator in the lyrics
            ";" - sample the lead note
            ":" : repeat the marked section
            'C' / 'c' : change the chord
            'D' / 'd' : delete row
            'E' / 'e' : export to MIDI
            'H' / 'h' : play just the MIDI
            'j' : shift down by half
            'k' : shift up by half
            'J' : clone down by half
            'K' : clone up by half
            'M' / 'm' : set a marker
                - Start with '*' or '-' for a "point" marker (currently normal markers unimplemented)
            'N' / 'n' : nudge explicitly
            'P' / 'p' : play Audio + MIDI
            'R' / 'r' : set note to REST
            'S' / 's' : save a backup
            'T' / 't' : mark as start of track
            'X' / 'x' : export as plain text
            'Y' / 'y' : export to Lilypond

        """
        spreader.register_key(self._do_play, "P", "p", arg="...slow", prompt="Playing...",
                            description="Play this file.")
        spreader.register_key(self._do_play_segment, "^J",
                              description="Go to and repeat")
        spreader.register_key(self._do_tap, ".",
                              description="Mark a beat")
        spreader.register_key(self._do_delete, "D", "d",
                              description="delete a row")
        spreader.register_key(self._do_jump, "@", arg="?str", prompt="What time code?",
                              description="Jump to or create by timecode")
        spreader.register_key(self._do_track, "t", "T",
                              description="Mark as start of track")
        spreader.register_key(self._do_lyric, '"', "L", 'l', arg="?str", prompt="Lyric?", query=True,
                              description="Enter lyric for this note")
        spreader.register_key(self._do_mark, "M", "m", arg="?str", prompt="How would you like to mark it?",query=True,
                              description="Mark this segment with some text.")
        spreader.register_key(self._do_chord, "c", "C",
                              description="Change the chord")
        spreader.register_key(self._do_play_chords, "h", "H",
                              description="Play just the chords")
        spreader.register_key(self._do_shift_down, "j","^N",
                              description="Shift this note half way between the current spot and the one below it.")
        spreader.register_key(self._do_shift_up, "k", "^P",
                              description="Shift this note half way between the current spot and the one above it.")
        spreader.register_key(self._do_clone_down, "J",
                              description="Clone this note half way between the current spot and the one below it.")
        spreader.register_key(self._do_clone_up, "K",
                              description="Clone this note half way between the current spot and the one above it.")
        spreader.register_key(self._do_export_midi, "E", "e", arg="?str",
                            prompt="Export to MIDI (^G to cancel; ENTER to name 'export.midi'.]",
                            description="Export to MIDI")
        spreader.register_key(self._do_export_lily, "Y", "y", arg="?str",
                            prompt="Export to Lilypond (^G to cancel; ENTER to name 'export.ly'.]",
                            description="Export to Lilypond file")
        spreader.register_key(self._do_export_txt, "X", "x", arg="?str",
                            prompt="Export to plain text  (^G to cancel; ENTER to name 'export.txt'.]",
                            description="Export to text file")
        spreader.register_key(self._do_backup, "S", "s", arg="...slow", prompt="Backing up...",
                              description="Save a backup of the song data")
        spreader.register_key(self._do_line_mark, "/",
                              description="change the line separator indicator in the lyrics")
        spreader.register_key(self._do_up_octave, "'",
                              description="Push the lead note up an octave")
        spreader.register_key(self._do_down_octave, ",",
                              description="Push the lead note down an octave")
        spreader.register_key(self._do_up_note, "}",
                              description="Push the lead note up an octave")
        spreader.register_key(self._do_down_note, "{",
                              description="Push the lead note down an octave")
        spreader.register_key(self._do_up_on_scale, "]",
                              description="Push the lead note up an octave")
        spreader.register_key(self._do_down_on_scale, "[",
                              description="Push the lead note down an octave")
        spreader.register_key(self._do_sample_note, ";",
                              description="Sample the current lead note")
        spreader.register_key(self._do_lead_rest, "R", "r",
                              description="Set lead note to rest")
        spreader.register_key(self._do_nudge, "N", "n", arg="?str", prompt="Nudge the current line up or down in seconds:",
                              description="Nudge this note explicitly between the current spot and the two around it it.")
        spreader.register_key(self._do_repeat_mark, ":",
                              description="Repeat the marked section")
        spreader.register_key(self._do_beat_repeat, "B", "b", arg="?str",
                              prompt="How many and at what rate? (like: 6x120bpm or 3x2@120bpm")

    def scan(self):
        self.import_file = self.config["instance"]["import-file"]
        self.bits = self.import_lister.get(self.import_file)
        self.data_file = Path(self.bits["metadata"]).with_suffix(".data")
        self.metadata = ConfigParser(inline_comment_prefixes=None)
        self.metadata.read(str(self.bits["metadata"]))

        if self.data_file.exists():
            with self.data_file.open(newline="") as csvfile:
                data_reader = csv.DictReader(csvfile, dialect=ImportCsvDialect)
                for row in data_reader:
                    location = float(row["location"])
                    row["location"] = location
                    self.data[location] = row
        if len(self.data) == 0:
            self.add_row(0.0, mark="START")
            self.add_row(self.bits["length_secs"], mark="END")
        self.update_order()
        self.clean()

    def add_row(self, location, *, mark=""):
        if location in self.data:
            raise IndexError("location {} already present in data".format(location))
        if self.order and location > self.order[-1]:
            raise IndexError("location {} can't be bigger than file".format(location))
        if location < 0:
            raise IndexError("location {} can't be less than zero".format(location))
        row = {"location":location, "mark":mark, "lyric":"", "track_ui":"", "chord_ui":"",
               "chord-change":"", "track-change":"", "note":"", "note_ui":"-"}
        self.data[location]  = row
        return row

    def update_order(self):
        self.order = list(self.data.keys())
        self.order.sort()
        self.save()

    def clean(self):
        for r in self.data.values():
            r.setdefault("lyric", "")
            r.setdefault("chord-change", "")
            r.setdefault("track-change", "")
            r.setdefault("note", "")
            note = r.get("note", "")
            if note == "":
                r["note_ui"] = "-"
            else:
                r["note_ui"] = getLyForMidiNote(note)

        self._propagate()

    def find_song_data(self, song):
        ret = {}
        ret.update(self.config["preset_0"])
        if str(song) in self.metadata:
            song_meta = self.metadata[str(song)]
        else:
            song_meta = {}
        for k in song_meta.keys():
            if song_meta[k].strip() != "":
                ret[k] = song_meta[k]
        ret["key_note"] = int(ret.get("key","60"))
        ret["scale_parsed"] = parse_scale(ret.get("scale", "1 2 3 4 5 6 7").strip())
        ret["lead_instrument"] = int(ret.get("lead_instrument","0"))
        ret["pad_instrument"] = int(ret.get("pad_instrument","0"))
        ret["pad_offset"] = int(ret.get("pad_offset","-12"))
        ret["pad_chords_parsed"] = parse_chords(ret.get("pad_chords", "1"), ret["scale_parsed"], ret["key_note"] + ret["pad_offset"])
        ret["pad_chord_seq"] = parse_sequence(ret.get("pad_sequence", "I"), ret["pad_chords_parsed"])
        ret["pad_velocity"] = int(ret.get("pad_velocity", 64))
        ret["lead_velocity"] = int(ret.get("lead_velocity", 64))
        return ret

    def save(self):
        if not self.changed:
            return
        with self.data_file.open("w", newline='') as csvfile:
            fieldnames = ['location', 'lyric', 'mark', 'track-change', "chord-change", "note"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore', dialect=ImportCsvDialect)
            writer.writeheader()
            for location in self.order:
                writer.writerow(self.data[location])
        with open(str(self.bits["metadata"]), 'w') as meta:
            self.metadata.write(meta)

    def backup(self):
        dsecs = self.data_file.stat().st_mtime
        meta_file = Path(self.bits["metadata"])
        msecs = meta_file.stat().st_mtime
        secs = max(dsecs, msecs)
        suffix = filename_iso_time(secs)
        backup_data = self.data_file.with_name("{}-{}{}".format(self.data_file.stem, suffix, self.data_file.suffix))
        backup_meta = meta_file.with_name("{}-{}{}".format(meta_file.stem, suffix, meta_file.suffix))
        with backup_data.open("w", newline='') as csvfile:
            fieldnames = ['location', 'lyric', 'mark', 'track-change', "chord-change", "note"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore', dialect=ImportCsvDialect)
            writer.writeheader()
            for location in self.order:
                writer.writerow(self.data[location])
        with backup_meta.open('w') as meta:
            self.metadata.write(meta)

    def get_line(self, what, max_len):
        datum = self.data[what]
        padout=max_len - 23
        marklen = int(padout // 3)
        lyrlen = int(padout * 2 // 3)
        return "{human_time} {note_ui:5.5} {lyric:{lyrlen}.{lyrlen}} {chord_ui: >3.3} {track_ui: >3.3} {mark:{marklen}.{marklen}}".format(
            marklen=marklen, lyrlen=lyrlen,
            human_time=human_duration(datum["location"], floor=3), **datum)

    def get_order(self):
        return self.order

    def __call__(self, *args, **kwargs):
        pass

    def set_defaults_for_song(self, song):
        basis = self.find_song_data(song)
        out = self.metadata[str(song)]
        out["bpm"] = str(basis.get("bpm", "120"))
        out["lily_key"] = basis.get("lily_key", r"c \major")
        out["copyright"] = basis.get("copyright", "")
        if "tagline" in basis:
            out["tagline"] = basis["tagline"]
        out["poet"] = basis.get("poet", "")
        out["time"] = basis.get("time", "4/4")
        out["key"] = basis.get("key", "60")
        out["scale"] = basis.get("scale", "1 2 3 4 5 6 7")
        out["lead_instrument"] = str(basis.get("lead_instrument","0"))
        out["pad_instrument"] = str(basis.get("pad_instrument","0"))
        out["pad_offset"] = str(basis.get("pad_offset","-12"))
        out["pad_chords"] = basis.get("pad_chords", "1")
        out["pad_sequence"] = basis.get("pad_sequence", "I")
        out["pad_velocity"] = str(basis.get("pad_velocity", 64))
