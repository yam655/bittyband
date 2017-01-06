#!/usr/bin/env python3

__all__ = ["Lister"]

from pathlib import Path
import sys
import time
from configparser import ConfigParser
from .exportly import ExportLy
from .exportmidi import ExportMidi
from .commands import Commands

class Lister:
    def __init__(self, config):
        self.project_dir = Path(config["instance"]["project_dir"])
        self.proj_lists = self.project_dir / "cmd-streams.index"
        self.marks = ConfigParser()
        self.order = []
        self.config = config
        if self.proj_lists.exists():
            self.marks.read(str(self.proj_lists))
        else:
            self.scan()

    def get_order(self):
        return self.order

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
        cmds = Commands(self.config, exporter, None)
        exporter.start()
        cmds.play(self.get(what), realtime=False)
        exporter.end()

    def export_ly(self, what, output, title=""):
        exporter = ExportLy(self.config, output, title=title)
        cmds = Commands(self.config, exporter, None)
        exporter.start()
        cmds.play(self.get(what), realtime=False)
        exporter.end()

    def save(self): 
        with open(str(self.proj_lists), 'w') as projfile: 
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
                j = txt[line].split(",",1)
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


def human_duration(seconds):
    if seconds is None:
        return "?"
    if isinstance(seconds, str):
        seconds = float(seconds)

    tiny = "{:>.3f}".format(seconds % 1.0)[1:]
    s = "{:02d}{}".format(int(seconds) % 60, tiny)
    m = "00:"
    h = ""
    d = ""
    n = seconds // 60
    if n > 0:
        m = "{:02d}:".format(n % 60)
        n //= 60
    if n > 0:
        h = "{:02d}:".format(n % 24)
        n //=24
    if n > 0:
        d = "{}:".format(n)
    return "".join([d, h, m, s])

