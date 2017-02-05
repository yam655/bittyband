#!/usr/bin/env python3

import threading
import time
import queue

from mido import Message
from ..commands import LEAD_CHANNEL, PAD_CHANNEL


class CsvPlayer:
    def __init__(self, config):
        self.queue = queue.Queue()
        self.thread = None
        self.__line = 0
        self.last_track = None
        self.track_info = {}
        self.pad_note = None
        self.lead_note = None
        self.last_location = 0
        self.message_time = 0
        self.playing = False
        self.realtime = True
        self.skip_nap = False
        self.exporting = False

    def wire(self, *, importer, push_player, realtime=True, **kwargs):
        self.importer = importer
        self.player = push_player
        self.realtime = realtime

    def __del__(self):
        self.end()

    def start(self):
        if self.thread is None:
            self.thread = threading.Thread(target=self._runner, daemon=True)
            self.thread.start()

    def end(self):
        if self.queue is not None and self.thread is not None:
            self.queue.join()
            self.queue.put(None)
        pass

    def seek(self, line):
        self.__line = line
        self.last_location = 0
        self.playing = False

    line = property(lambda self: self.__line)

    def play(self):
        if self.__line >= len(self.importer.order):
            self.__line = 0
        self.playing = True
    def pause(self):
        self.playing = False

    def export(self):
        self.__line = 0
        self.exporting = True
        while self.__line < len(self.importer.order):
            self._play_line()

    def _play_line(self):
        global LEAD_CHANNEL
        global PAD_CHANNEL
        if not self.playing and not self.exporting:
            time.sleep(0.00001)
            return
        try:
            datum = self.importer.data[self.importer.order[self.__line]]
        except IndexError:
            if self.playing:
                self.__line = 0
            if len(self.importer.data) == 0:
                self.playing = False
                return
            datum = self.importer.data[self.importer.order[self.__line]]
        new_track = datum.get("track_id",-1)
        if self.last_location != 0:
            message_time = datum["location"] - self.last_location
        else:
            message_time = 0
        if not self.exporting and self.realtime and message_time > 0:
            time.sleep(message_time)
        else:
            self.message_time += int(message_time * 1000)
        if new_track != self.last_track:
            self.last_track = new_track
            self.track_info = self.importer.song_data[self.last_track]
            old_pad_note = self.pad_note
            old_lead_note = self.lead_note
            if old_pad_note is not None:
                self.set_pad_note()
            if old_lead_note is not None:
                self.set_lead_note()
            if self.last_track >= 0:
                self.player.new_track(**self.track_info)
            else:
                self.player.unknown_track()
            self.player.feed_midi(Message('program_change', channel=LEAD_CHANNEL,
                                          program=self.track_info["lead_instrument"], time=0))
            self.player.feed_midi(Message('program_change', channel=PAD_CHANNEL,
                                          program=self.track_info["pad_instrument"], time=0))
            if old_pad_note is not None:
                self.set_pad_note(old_pad_note)
            if old_lead_note is not None:
                self.set_lead_note(old_lead_note)
        self.last_location = datum["location"]

        if not self.playing and not self.exporting:
            return
        self.__line += 1
        if self.__line >= len(self.importer.order) and not self.exporting:
            self.__line = 0
        new_pad = datum.get("chord_value")
        if new_pad is not None:
            self.set_pad_note(new_pad)
        new_lead = datum.get("note")
        if new_lead is not None:
            self.set_lead_note(new_lead)
        self.send_lyric(datum["lyric"], self.lead_note is not None)

    def silence(self):
        self.playing = False
        self.set_lead_note()
        self.set_pad_note()

    def _runner(self):
        while True:
            if not self.queue.empty():
                message = self.queue.get()
                if message is None:
                    break
                self.queue.task_done()
            self._play_line()
        self.thread = None
        self.queue = None


    def set_lead_note(self, note=None):
        if isinstance(note, float):
            note = int(note)
        if isinstance(self.lead_note, int):
            self.player.feed_midi(Message('note_off', note=self.lead_note, channel=LEAD_CHANNEL, time=self.message_time))
            self.message_time = 0
        elif hasattr(self.lead_note, "__iter__"):
            note_set = []
            for pn in self.lead_note:
                note_set.append(Message('note_off', note=pn, channel=LEAD_CHANNEL))
            self.player.feed_midi(*note_set, time=self.message_time, abbr="chord_off")
            self.message_time = 0

        if isinstance(note, int):
            self.player.feed_midi(
                Message('note_on', note=note, channel=LEAD_CHANNEL, time=self.message_time, velocity=self.track_info.get("lead_velocity",64)))
            self.message_time = 0
        elif hasattr(note, "__iter__"):
            note_set = []
            for pn in note:
                note_set.append(Message('note_on', note=pn, channel=LEAD_CHANNEL, velocity=self.track_info["lead_velocity"]))
            if len(note) > 0:
                self.player.feed_midi(*note_set, time=self.message_time, abbr="chord_on")
            else:
                note = None
            self.message_time = 0
        self.lead_note = note

    def set_pad_note(self, note=None):
        if isinstance(note, float):
            note = int(note)
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
                Message('note_on', note=note, channel=PAD_CHANNEL, time=self.message_time, velocity=self.track_info.get("pad_velocity",64)))
            self.message_time = 0
        elif hasattr(note, "__iter__"):
            note_set = []
            for pn in note:
                note_set.append(Message('note_on', note=pn, channel=PAD_CHANNEL, velocity=self.track_info["pad_velocity"]))
            if len(note) > 0:
                self.player.feed_midi(*note_set, time=self.message_time, abbr="chord_on")
            else:
                note = None
            self.message_time = 0
        self.pad_note = note

    def send_lyric(self, lyric, need_spacer = False):
        if lyric is None:
            if need_spacer:
                self.player.feed_lyric("_")
            return
        self.player.feed_lyric(lyric)


