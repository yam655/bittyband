#!/usr/bin/env python3

"""Handle import of audio files"""

import sndhdr
from pathlib import Path
from configparser import ConfigParser


class ImporterBackend:
    order = []

    def __init__(self, config):
        self.project_dir = Path(config["instance"]["project_dir"])

    def scan(self):
        self.order = []
        import_dir = self.project_dir / "imports"
        if not import_dir.exists():
            return
        for f in import_dir.glob("*.wav"):
            metadata_file = f.with_suffix(".meta")
            # data_file = f.with_suffix(".csv")
            meta = ConfigParser()
            if metadata_file.exists():
                meta.read(filenames=str(metadata_file))
            if "audio" not in meta:
                meta.add_section("audio")

                what = sndhdr.what(str(metadata_file))
                if what is None:
                    continue
                meta["audio"]["filetype"] = what[0]
                meta["audio"]["framerate"] = what[1]
                meta["audio"]["nchannels"] = what[2]
                meta["audio"]["nframes"] = what[3]
                meta["audio"]["sampwidth"] = what[4]

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
