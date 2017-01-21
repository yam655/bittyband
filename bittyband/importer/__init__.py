#!/usr/bin/env

import csv
from pathlib import Path
from configparser import ConfigParser

import pyglet

from .csvplayer import CsvPlayer
from ..utils.cmdutils import *
from ..utils.time import human_duration, from_human_duration
from .importcsvdialect import ImportCsvDialect


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

    def wire(self, *, ui, import_lister, csv_player, **kwargs):
        self.ui = ui
        self.import_lister = import_lister
        self.csv_player = csv_player

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
        if self.csv_player.playing:
            self.csv_player.pause()
            self.csv_player.silence()
        else:
            self.csv_player.silence()
            self.csv_player.seek(self.start_line)
            self.csv_player.play()

    def _do_play_segment(self, *, line):
        if line == len(self.order) - 1:
            self.spreader.show_status("Can not play last segment")
            return False
        self.start_segment = self.order[line]
        self.start_line = line
        self.end_segment = self.order[line + 1]
        self.spreader.show_status("Playing: {} to {}".format(human_duration(self.start_segment), human_duration(self.end_segment)))
        self.player.seek(self.start_segment)
        self.csv_player.seek(self.start_line)
        if not self.player.playing:
            self.player.play()
        if not self.csv_player.playing:
            self.csv_player.play()

    def _do_delete(self, *, line):
        if line == 0 or line == len(self.order) - 1:
            self.spreader.show_status("Can't delete top or bottom")
            return False
        item = self.order[line]
        del self.data[item]
        del self.order[line]
        self.spreader.invalidate = True
        return True

    def _do_idle(self):
        if not self.player:
            self.spreader.show_status(self.bits["title"])
            self._start_player()
        t = self.player.time
        if self.end_segment is not None and t >= self.end_segment:
            self.player.seek(self.start_segment)
            self.csv_player.seek(self.start_line)
            self.player.play()
            self.csv_player.play()
        display = human_duration(t, floor=True)
        self.spreader.display_time(display)
        display = human_duration(self.order[self.csv_player.line-1], floor=1)
        self.spreader.display_line(display)
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
        return True

    _chord_options = ["", "chord", "rest", "resume"]
    def _do_chord(self, *, line):
        datum = self.data[self.order[line]]
        got = datum.get("chord-change","")
        if got == "":
            last = ""
            for i in range(line - 1, -1, -1):
                d = self.data[self.order[line]]
                last = d.get("chord-change", "")
                if last != "":
                    got = last
                    break

        idx = self._chord_options.index(got)
        idx += 1
        if idx >= len(self._chord_options):
            idx = 0
        datum["chord-change"] = self._chord_options[idx]
        self._need_propagate = True
        self.spreader.refresh_line(line)
        return True

    def _propagate(self):
        self._need_propagate = False
        last_track = "unknown"
        last_chord = "rest"
        self._tracks = []
        chord_idx = -1
        this_track = self.find_song_data(-1)
        self.song_data[-1] = this_track
        chord_values = this_track["pad_chord_seq"]
        for location in self.order:
            datum = self.data.get(location)
            next_track = datum.get("track-change", "")
            next_chord = datum.get("chord-change", "")
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

    def _do_jump(self, timecode, *, line):
        location = from_human_duration(timecode)
        if location is None:
            self.spreader.show_status("Invalid timecode: {}".format(timecode))
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
        self.data[self.order[line]]["lyric"] = lyric
        return True

    def _do_mark(self, mark, *, line):
        self.data[self.order[line]]["mark"] = mark
        return True

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
        data_from = self.data[from_loc]
        data_to = self.data[to_loc]
        for k in data_from.keys():
            if k == "location":
                continue
            data_to[k], data_from[k] = data_from[k], data_to.get(k,"")

    def prepare_keys(self, spreader):
        self.spreader = spreader
        spreader.register_idle(self._do_idle)
        spreader.on_exit(self.save)
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
        spreader.register_key(self._do_lyric, '"', "L", 'l', arg="?str", prompt="Lyric?",
                              description="Enter lyric for this note")
        spreader.register_key(self._do_mark, "M", "m", arg="?str", prompt="How would you like to mark it?",
                              description="Mark this segment with some text.")
        spreader.register_key(self._do_chord, "c", "C",
                              description="Change the chord")
        spreader.register_key(self._do_play_chords, "h", "H",
                              description="Play just the chords")
        spreader.register_key(self._do_shift_down, "j", "J", "^N",
                              description="Shift this note half way between the current spot and the one below it.")
        spreader.register_key(self._do_shift_up, "k", "K", "^P",
                              description="Shift this note half way between the current spot and the one above it.")

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
        row = {"location":location, "mark":mark, "lyric":"", "track_ui":"", "chord_ui":"",
               "chord-change":"", "track-change":"", "note":""}
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
        self._propagate()

    def find_song_data(self, song):
        ret = {}
        ret.update(self.config["preset_0"])
        if str(song) in self.metadata:
            song_meta = self.metadata[str(song)]
        else:
            song_meta = {}
        for k in song_meta.keys():
            if k not in ret or song_meta[k].strip() != "":
                ret[k] = song_meta[k]

        ret["key_note"] = int(ret.get("key","60"))
        ret["scale_parsed"] = parse_scale(ret.get("scale", "1 2 3 4 5 6 7").strip())
        ret["lead_instrument"] = int(ret.get("lead_instrument","0"))
        ret["pad_instrument"] = int(ret.get("pad_instrument","0"))
        ret["pad_offset"] = int(ret.get("pad_offset","-12"))
        ret["pad_chords_parsed"] = parse_chords(ret.get("pad_chords", "1"), ret["scale_parsed"], ret["key_note"] + ret["pad_offset"])
        ret["pad_chord_seq"] = parse_sequence(ret.get("pad_sequence", "I"), ret["pad_chords_parsed"])
        ret["pad_velocity"] = int(ret.get("pad_velocity", 64))
        return ret

    def save(self):
        with self.data_file.open("w", newline='') as csvfile:
            fieldnames = ['location', 'lyric', 'mark', 'track-change', "chord-change", "note"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore', dialect=ImportCsvDialect)
            writer.writeheader()
            for location in self.order:
                writer.writerow(self.data[location])
        with open(str(self.bits["metadata"]), 'w') as meta:
            self.metadata.write(meta)

    def get_line(self, what, max_len):
        datum = self.data[what]
        padout=max_len - 18
        marklen = int(padout // 3)
        lyrlen = int(padout * 2 // 3)
        return "{human_time} {lyric:{lyrlen}.{lyrlen}} {chord_ui: >3.3} {track_ui: >3.3} {mark:{marklen}.{marklen}}".format(
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
        out["pad_chord_seq"] = basis.get("pad_sequence", "I")
        out["pad_velocity"] = str(basis.get("pad_velocity", 64))
