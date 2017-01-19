#!/usr/bin/env

import csv
from pathlib import Path
import time
from configparser import ConfigParser

import pyglet

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
        self.end_segment = None

    def wire(self, *, ui, import_lister, **kwargs):
        self.ui = ui
        self.import_lister = import_lister


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

    def _do_play(self, line, repeat=False):
        self.start_segment = self.order[line]
        if self.player.time < self.start_segment:
            self.player.seek(self.start_segment)
        self.end_segment = None
        if repeat == True:
            self.end_segment = self.play_length
        if self.player.playing:
            self.player.pause()
        elif self.player.time >= self.play_length:
            self.player.seek(0)
            self.player.play()
        else:
            self.player.play()

    def _do_play_segment(self, *, line):
        if line == len(self.order) - 1:
            self.spreader.show_status("Can not play last segment")
            return False
        self.start_segment = self.order[line]
        self.end_segment = self.order[line + 1]
        self.spreader.show_status("Playing: {} to {}".format(human_duration(self.start_segment), human_duration(self.end_segment)))
        self.player.seek(self.start_segment)
        if not self.player.playing:
            self.player.play()

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
            self.player.play()
        display = human_duration(t, floor=True)
        self.spreader.display_time(display)
        if not self.player.playing:
            if len(self.order) != len(self.data):
                self.update_order()
                self.spreader.refresh()
            if self._need_propagate:
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
        idx = self._track_change_states.index(got)
        idx += 1
        if idx >= len(self._track_change_states):
            idx = 0
        datum["track-change"] = self._track_change_states[idx]
        self._need_propagate = True
        self.spreader.refresh_line(line)
        return True

    def _propagate(self):
        self._need_propagate = False
        last = "unknown"
        self._tracks = []
        for location in self.order:
            datum = self.data.get(location)
            next = datum.get("track-change", "")
            if next == "":
                if last == "unknown":
                    datum["track_ui"] = "  ?"
                    datum["track_id"] = -1
                elif last == "track":
                    datum["track_id"] = self._tracks[-1]
                    datum["track_ui"] = " {:02d}".format(len(self._tracks))
                elif last == "crap":
                    datum["track_ui"] = "  -"
                    datum["track_id"] = -1
            elif next == "unknown":
                datum["track_ui"] = "? ?"
                datum["track_id"] = -1
                last = next
            elif next == "track":
                last = next
                self._tracks.append(datum["location"])
                datum["track_id"] = self._tracks[-1]
                datum["track_ui"] = "*{:02d}".format(len(self._tracks))
            elif next == "crap":
                last = next
                datum["track_ui"] = "- -"
                datum["track_id"] = -1
            elif next == "resume":
                if len(self._tracks) == 0:
                    datum["track_ui"] = "/ ?"
                    datum["track_id"] = -1
                    last = "unknown"
                else:
                    datum["track_id"] = self._tracks[-1]
                    datum["track_ui"] = "+{:02d}".format(len(self._tracks))
                    last = "track"
        self.metadata["audio"]["tracks"] = str(len(self._tracks))
        for t in self._tracks:
            if str(t) not in self.metadata:
                self.metadata.add_section(str(t))
            if self.data[t].get("mark","") == "":
                self.data[t]["mark"] = "Track @{}".format(human_duration(t,0))
            self.metadata[str(t)]["title"] = self.data[t]["mark"]

    def _do_jump(self, timecode, *, line):
        location = from_human_duration(timecode)
        if location is None:
            self.spreader.show_status("Invalid timecode: {}".format(timecode))
        else:
            newline = None
            if location in self.data:
                try:
                    newline = self.order.index(location)
                except ValueError:
                    self.update_order()
                    newline = self.order.index(location)
            if newline is None:
                was_playing = self.player.playing
                self.add_row(location)
                if was_playing:
                    self.player.pause()
                self.player.seek(location)
                self._do_idle()
                if was_playing:
                    self.player.play()
                newline = self.order.index(location)
            self.spreader.active = newline
            self.spreader.refresh()

    def _do_lyric(self, lyric, *, line):
        self.data[self.order[line]]["lyric"] = lyric
        return True

    def _do_mark(self, mark, *, line):
        self.data[self.order[line]]["mark"] = mark
        return True

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
        row = {"location":location, "mark":mark, "lyric":"", "track_ui":""}
        self.data[location]  = row
        return row

    def update_order(self):
        self.order = list(self.data.keys())
        self.order.sort()
        self.save()

    def clean(self):
        for r in self.data.values():
            if "lyric" not in r:
                r["lyric"] = ""
        self._propagate()

    def save(self):
        with self.data_file.open("w", newline='') as csvfile:
            fieldnames = ['location', 'lyric', 'mark', 'track-change']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore', dialect=ImportCsvDialect)
            writer.writeheader()
            for location in self.order:
                writer.writerow(self.data[location])
        with open(str(self.bits["metadata"]), 'w') as meta:
            self.metadata.write(meta)

    def get_line(self, what, max_len):
        datum = self.data[what]
        padout=max_len - 15
        marklen = int(padout // 3)
        lyrlen = int(padout * 2 // 3)
        return "{human_time} {lyric:{lyrlen}.{lyrlen}} {track_ui: >3.3} {mark:{marklen}.{marklen}}".format(
            marklen=marklen, lyrlen=lyrlen,
            human_time=human_duration(datum["location"], floor=3), **datum)

    def get_order(self):
        return self.order

    def __call__(self, *args, **kwargs):
        pass