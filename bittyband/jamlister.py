#!/usr/bin/env python3

from pathlib import Path
import time
from configparser import ConfigParser

from .bgplayer import BackgroundNull
from .exportly import ExportLy
from .exportmidi import ExportMidi
from .commands import Commands
from .utils.time import human_duration


class JamLister:

    def __init__(self, config):
        self.config = config
        self.project_dir = Path(config["instance"]["project_dir"])
        self.streams_index = self.project_dir / "cmd-streams.index"
        self.marks = ConfigParser()
        self.order = []
        if self.streams_index.exists():
            self.marks.read(str(self.streams_index))
        else:
            self.scan()

    def wire(self, *, push_commands, **kwargs):
        self.commands = push_commands

    def _do_rename(self, title, line):
        if title == "" or title is None:
            self.rename(self.get_order()[line], "")
        else:
            self.rename(self.get_order()[line], title)
        return True

    def _do_play(self, line):
        material = self.get(self.get_order()[line])
        self.commands.play(material)
        self.commands.background.pause()
        return False

    def _do_delete(self, line):
        self.delete(self.get_order()[line])
        return True

    def _do_export_midi(self, filename, line):
        mark = self.get_mark(self.get_order()[line])
        if filename is None or len(filename.strip()) == 0:
            self.export_midi(self.get_order()[line],
                             self.project_dir / "{}.midi".format(mark.get("title", "export")))
        else:
            self.export_midi(self.get_order()[line], self.project_dir / filename)
        return False

    def _do_export_lily(self, filename, line):
        mark = self.get_mark(self.get_order()[line])
        title = mark.get("title", "Untitled")
        if filename is None or len(filename.strip()) == 0:
            self.export_ly(self.get_order()[line],
                           self.project_dir / "{}.ly".format(mark.get("title", "export")),
                           title=title)
        else:
            self.export_ly(self.get_order()[line], self.project_dir / filename, title=title)
        return False

    def prepare_keys(self, lister):
        lister.register_key(self._do_rename, "R", "r", arg="?str",
                            prompt="New title?",
                            description="Rename the current marked segment")
        lister.register_key(self._do_play, "P", "p", arg="...slow",
                            prompt="Playing...",
                            description="Play the current marked segment")
        lister.register_key(self._do_delete, "D", "d", arg="?yN",
                            prompt="Really delete? (y/N)",
                            description="Delete the current marked segment")
        lister.register_key(self._do_export_midi, "M", "m", arg="?str",
                            prompt="Export to MIDI (^G to cancel; ENTER to name based on segment.]",
                            description="Export to MIDI")
        lister.register_key(self._do_export_lily, "Y", "y", "L", "l", arg="?str",
                            prompt="Export to Lilypond (^G to cancel; ENTER to name based on segment.]",
                            description="Export to Lilypond file")

    def get_order(self):
        return self.order

    def get_line(self, bit, max_len):
        return self.get_title(bit, max_len)

    def get_mark(self, what):
        return self.marks[what]

    def rename(self, what, name):
        n = self.get_mark(what)
        if name is None or len(name) == 0:
            del n["title"]
        else:
            n["title"] = name
        self.save()

    def delete(self, what):
        n = self.get_mark(what)
        n["state"] = "deleted"
        self.save()
        self.scan()

    def get(self, what):
        n = self.get_mark(what)
        fname = self.project_dir / n["name"]
        txt = fname.read_text().split("\n")
        s = int(n["start"])
        e = int(n["end"])
        return txt[s:e]

    def export_midi(self, what, output):
        exporter = ExportMidi(self.config, output)
        cmds = Commands(self.config)
        cmds.wire(push_player=exporter, metronome=BackgroundNull())
        exporter.start()
        cmds.play(self.get(what), realtime=False)
        exporter.end()

    def export_ly(self, what, output, title=""):
        exporter = ExportLy(self.config, output, title=title)
        cmds = Commands(self.config)
        cmds.wire(push_player=exporter, metronome=BackgroundNull())
        exporter.start()
        cmds.play(self.get(what), realtime=False)
        exporter.end()

    def save(self):
        with open(str(self.streams_index), 'w') as projfile:
            self.marks.write(projfile)

    def get_title(self, what, width=None):
        n = self.get_mark(what)
        title = n.get("title", "Untitled: " + what)
        secs = float(n["timestamp_secs"])
        suffix = " ({}) [{}]".format(time.asctime(time.localtime(secs)), human_duration(n["length"]))
        if width is None:
            return title + suffix
        title = "{0:{width}.{width}}{1}".format(title, suffix, width=width-len(suffix))
        return title

    def scan(self):
        self.order = []
        for f in self.project_dir.glob("cmd-*.stream"):
            txt = f.read_text().split("\n")
            marks = 0
            line = 0
            line_start = None
            start_secs = 0.0
            while line < len(txt):
                j = txt[line].split(",", 1)
                cmd = j[-1]
                if cmd == "mark_bad":
                    line_start = line + 1
                    start_secs = float(j[0])
                if cmd.startswith("mark_good") or cmd == "next":
                    if line_start is not None:
                        n = "{}-{}-{}".format(f.name, line_start, line)
                        if not self.marks.has_section(n):
                            self.marks.add_section(n)
                        if self.marks[n].get("state") != "deleted":
                            self.order.append(n)
                            end_secs = float(j[0])
                            self.marks[n]["name"] = f.name
                            self.marks[n]["start"] = str(line_start)
                            self.marks[n]["end"] = str(line+1)
                            self.marks[n]["length"] = str(end_secs - start_secs)
                            self.marks[n]["timestamp_secs"] = f.name[len("cmd-"):-len(".stream")]
                            marks += 1
                    start_secs = float(j[0])
                    line_start = line + 1
                line += 1
            if marks == 0:
                f.unlink()
        self.save()

