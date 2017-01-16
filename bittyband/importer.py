#!/usr/bin/env python3

"""Handle import of audio files"""

from pathlib import Path
from configparser import ConfigParser

import taglib
import pyglet
import time

from .utils.time import human_duration, reasonable_time

class ImporterBackend:
    order = []
    data = {}
    ui = None
    player = None
    last_player_time = None
    play_length = None

    def __init__(self, config):
        self.project_dir = Path(config["instance"]["project_dir"])

    def wire(self, *, ui, **kwargs):
        self.ui = ui

    def _play_status(self):
        if not self.player:
            return None
        t = self.player.time
        if t >= self.play_length:
            return None
        self.last_player_time = t
        return human_duration(t, floor=True)

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

    def _do_play(self, line):
        datum = self.data[self.order[line]]
        media = self.project_dir / "import" / datum["media"]
        media = media.resolve()
        self.play_length = datum["length_secs"]
        sound = pyglet.media.load(str(media))
        group = pyglet.media.SourceGroup(sound.audio_format, sound.video_format)
        group.queue(sound)
        self.player = pyglet.media.Player()
        self.player.queue(group)
        self.player.play()
        time.sleep(0.1)
        self.ui.play_ui(self._play_status, seek=self._play_live_seek)
        self.player.pause()

    def prepare_keys(self, lister):
        # lister.register_key(self._do_rename, "R", "r", arg="?str",
        #                     prompt="New title?",
        #                     description="Rename the current marked segment")
        lister.register_key(self._do_play, "P", "p", arg="...slow", prompt="Playing...",
                            description="Play this file.")

    def get_order(self):
        return self.order

    def get_line(self, bit, max_len):
        n = self.data[bit]
        title = n.get("title", "Untitled: " + bit)

        if n.get("unprocessed_length") is not None:
            prefix = "[{}] ".format(n["unprocessed_length"])
        elif n.get("tracks", 0) > 0:
            tracks = "tracks"
            if n["tracks"] == 1:
                tracks = "track "
            prefix = "[{:2d} {}] ".format(n["tracks"], tracks)
        else:
            prefix = "[untouched] "

        suffix = " {} [{}]".format(n["timestamp"], n["total_length"])
        if max_len is None:
            return prefix + title + suffix
        width = max_len - len(suffix) - len(prefix)
        line = "{0}{1:{width}.{width}}{2}".format(prefix, title, suffix, width=width)
        return line

    def scan(self):
        self.order = []
        import_dir = self.project_dir / "imports"
        if not import_dir.exists():
            return
        self.data = {}
        for f in import_dir.glob("*.[mM][pP]3"):
            metadata_file = f.with_suffix(".meta")
            # data_file = f.with_suffix(".csv")
            lyrics_file = f.with_suffix(".txt")
            media_file = f.resolve()
            meta = ConfigParser()
            if metadata_file.exists():
                meta.read(filenames=str(metadata_file))
            if "audio" not in meta:
                meta.add_section("audio")

                stat = media_file.stat()
                early_stamp = stat.st_ctime
                if early_stamp is None or early_stamp == 0 or early_stamp > stat.st_mtime:
                    early_stamp = stat.st_mtime
                meta["audio"]["created"] = str(early_stamp)
                meta["audio"]["modified"] = str(stat.st_mtime)
                meta["audio"]["size"] = str(stat.st_size)

                what = taglib.File(str(media_file))
                if "ARTIST" in what.tags:
                    meta["audio"]["artist"] = flatten_tag(what.tags["ARTIST"])
                fallback_title = "{} from {}".format(metadata_file.stem, reasonable_time(early_stamp))
                if "TITLE" in what.tags:
                    meta["audio"]["title"] = flatten_tag(what.tags["TITLE"], truncate=True, fallback=fallback_title)
                else:
                    meta["audio"]["title"] = fallback_title
                if "ALBUM" in what.tags:
                    meta["audio"]["album"] = flatten_tag(what.tags["ALBUM"], truncate=True)
                if "DATE" in what.tags:
                    meta["audio"]["date"] = flatten_tag(what.tags["DATE"], truncate=True)
                meta["audio"]["sample_rate"] = str(what.sampleRate)
                meta["audio"]["channels"] = str(what.channels)
                meta["audio"]["length"] = str(what.length)
                meta["audio"]["bit_rate"] = str(what.bitrate)
                meta["audio"]["tracks"] = "0"

                if "LYRICS:NONE" in what.tags and not lyrics_file.exists():
                    lyrics = flatten_tag(what.tags["LYRICS:NONE"], separator=r"\n\n-----\n\n")
                    lyrics_file.write_text(lyrics.replace(r"\n","\n"))
                if lyrics_file.exists():
                    meta["audio"]["lyrics"] = lyrics_file.name
                with open(str(metadata_file), 'w') as out:
                    meta.write(out)

            title = meta["audio"]["title"]
            length_secs = float(meta["audio"]["length"])
            total_length = human_duration(length_secs)
            timestamp =  reasonable_time(float(meta["audio"]["created"]))
            tracks = int(meta["audio"]["tracks"])
            unprocessed_length = None
            if "unprocessed_length" in meta["audio"]:
                unprocessed_length = human_duration(float(meta["audio"]["unprocessed_length"]))

            self.order.append(metadata_file.stem)
            self.data[metadata_file.stem] = {
                "media": str(media_file),
                "title": title,
                "total_length": total_length,
                "length_secs": length_secs,
                "timestamp": timestamp,
                "tracks": tracks,
                "unprocessed_length": unprocessed_length,
            }

        return self.order

def flatten_tag(tag_list, truncate = False, fallback = "", separator = " // "):
    if tag_list is None:
        return fallback
    if len(tag_list) == 1 or truncate:
        check = tag_list[0].strip()
        if check == "":
            return fallback
        return check
    out = []
    for t in tag_list:
        t = t.strip()
        if t == "":
            continue
        if len(out) > 0:
            if out[-1] != t:
                out.append(t)
    if len(out) == 0:
        return fallback
    return separator.join(out)
