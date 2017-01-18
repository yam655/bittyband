#!/usr/bin/env

import csv
from pathlib import Path
import time

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
        return True

    def _do_idle(self):
        if not self.player:
            self.spreader.show_status(self.bits["title"])
            self._start_player()
        t = self.player.time
        if self.end_segment is not None and t >= self.end_segment-1:
            self.player.seek(self.start_segment)
            self.player.play()
        display = human_duration(t, floor=True)
        self.spreader.display_time(display)
        if not self.player.playing:
            if len(self.order) != len(self.data):
                self.update_order()
                self.spreader.refresh()

    def _do_tap(self, *, line):
        offset = self.player.time
        if offset not in self.data:
            self.add_row(offset)
        self.spreader.show_status(human_duration(offset, 3))

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
        spreader.register_key(self._do_delete, "d",
                              description="delete a row")
        spreader.register_key(self._do_jump, "@", arg="?str", prompt="What time code?",
                              description="Jump to or create by timecode")

    def scan(self):
        self.import_file = self.config["instance"]["import-file"]
        self.bits = self.import_lister.get(self.import_file)
        self.data_file = Path(self.bits["metadata"]).with_suffix(".data")
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

    def add_row(self, location, *, mark=""):
        if location in self.data:
            raise IndexError("location {} already present in data".format(location))
        row = {"location":location, "mark":mark}
        self.data[location]  = row
        return row

    def update_order(self):
        self.order = list(self.data.keys())
        self.order.sort()
        self.save()

    def save(self):
        with self.data_file.open("w", newline='') as csvfile:
            fieldnames = ['location', 'mark']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, dialect=ImportCsvDialect)
            writer.writeheader()
            for location in self.order:
                writer.writerow(self.data[location])

    def get_line(self, what, max_len):
        datum = self.data[what]
        return "{human_time} {mark:20.20}".format(human_time=human_duration(datum["location"], floor=3), **datum)

    def get_order(self):
        return self.order

    def __call__(self, *args, **kwargs):
        pass