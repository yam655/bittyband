#!/usr/bin/env python3
import json
from configparser import ConfigParser
from pathlib import Path

import mido

from .automate import Automate
from ..exportly import ExportLy
from ..exportmidi import ExportMidi
from ..exporttxt import ExportTxt
from .commands import BeaterCommands
from .beatbox import BeatBox
from .beatplayer import BeatPlayer

class Beater:
    def __init__(self, config):
        self.config = config
        self.beat_box = None
        self.ui = None
        self.player = None
        self.start_segment = None
        self.start_line = 0
        self.end_segment = None
        self.song_data = {}
        self.last_note = None
        self.playing_row = None
        self.beat_player = None
        self.push_player = None
        self.beater_commands = BeaterCommands(self)

    def wire(self, *, ui, import_lister, beat_player, push_player, **kwargs):
        self.beater_commands.wire(ui=ui, import_lister=import_lister, beat_player=beat_player, push_player=push_player)
        self.ui = ui
        self.import_lister = import_lister
        self.beat_player = beat_player
        self.push_player = push_player

    # def _start_player(self):
        # media = self.bits["media"]
        # self.play_length = self.bits["length_secs"]

    def export_midi(self, output):
        exporter = ExportMidi(self.config, output)
        beatplayer = BeatPlayer(self.config)
        beatplayer.wire(importer=self, push_player=exporter, realtime=False)
        exporter.start()
        beatplayer.export()
        exporter.end()

    def export_txt(self, output):
        exporter = ExportTxt(self.config, output)
        beatplayer = BeatPlayer(self.config)
        beatplayer.wire(importer=self, push_player=exporter, realtime=False)
        exporter.start()
        beatplayer.export()
        exporter.end()

    def export_ly(self, output):
        exporter = ExportLy(self.config, output)
        beatplayer = BeatPlayer(self.config)
        beatplayer.wire(importer=self, push_player=exporter, realtime=False)
        exporter.start()
        beatplayer.export()
        exporter.end()

    def prepare_keys(self, spreader):
        self.spreader = spreader
        self.beater_commands.prepare_keys(spreader)

    def prepare(self, import_file):
        self.import_file = import_file

    def scan(self):
        bits = self.import_lister.get(self.import_file)
        self.beat_box = BeatBox(self.config, self.import_file, bits)
        # self.beat_box.update_order()
        # self.beat_box.clean()
        Automate().process(self.beat_box)

    def return_value(self, line):
        return False

    def get_line(self, what, max_len):
        return self.beat_box.get_line(what, max_len)

    def get_order(self):
        return self.beat_box.get_order()

    def __call__(self, *args, **kwargs):
        pass

