#!/bin/env python3

__all__ = ["parse", "get_config", "get_project_dir"]

from configparser import ConfigParser
import argparse
from pathlib import Path
import sys

""" The sum total of the built-in, user and project configuration """
config = ConfigParser()
""" The active project's base directory """
project_dir = None

def get_config():
    global config
    return config

def get_project_dir():
    global project_dir
    return project_dir

def parse(argv): 
    global config
    global parser
    if len(argv) == 0:
        args = parser.parse_args(["gui"])
    else:
        args = parser.parse_args(argv)
    if hasattr(args,"func"):
        if args.func(args):
            sys.exit(0)
    config = load_project_config(args)
    if hasattr(args,"mode"):
        config["project"]["mode"] = args.mode
    else:
        config["project"]["mode"] = ""
    return config

default_config = r"""
[DEFAULT]
# MIDI standard G4
key = 67
# Major scale
scale = rel: 1 2 3 4 5 6 7
# 57:"Trumpet",
lead_instrument = 57
lead_mode = serial-note
lead_chords = 1 3 5
# 83:"Lead 3 (calliope)",
pad_instrument = 83
pad_mode = serial-chord
# 50s progression
pad_sequence = I-vi-IV-V
pad_chords = 1 3 5

[preset_0]

[preset_1]
# pragmatic C4
key = 72
# Major scale
# scale = rel: 1 2 3 4 5 6 7

[preset_2]
# MIDI standard G4
key = 67
# Major scale
scale = rel: 1 2 3 4 5 6 7

[preset_3]
# https://en.wikipedia.org/wiki/Acoustic_scale
scale = rel: 1 2 3 #4 5 6 b7

[preset_4]
# Aeolian mode or natural minor scale
scale = rel: 1 2 b3 4 5 b6 b7 

[preset_5]
# Yo scale
scale = rel:  1 b3 4 5 b7

[preset_6]
# Prometheus scale
scale = rel:  1 2 3 #4 6 b7 

[preset_7]
# Blues scale
scale = rel:  1 b3 4 b5 5 b7 
# 12 Bar Blues
pad_sequence = I7-I7-I7-I7-IV7-IV7-I7-I7-V7-IV7-I7-V7

[preset_8]
scale = rel: 1 b3 3 5 #5 7

[preset_9]
key = 60 # MIDI standard C4
scale = rel: 1 2 3 4 5 6 7


[keymap]
quit = (^[,KEY_ESCAPE,\N{escape})
note_blip = "'"
preset_0 = 0
preset_1 = 1
preset_2 = 2
preset_3 = 3
preset_4 = 4
preset_5 = 5
preset_6 = 6
preset_7 = 7
preset_8 = 8
preset_9 = 9
mark_bad = (^H,^?,KEY_BACKSPACE,\N{delete},\N{backspace}) 
mark_good = (^I,\N{Character Tabulation})
note_steps-12 = "q"
note_steps-11 = "w"
note_steps-10 = "e"
note_steps-9 = "r"
note_steps-8 = "t"
note_steps-7 = "y"
note_steps-6 = "u"
note_steps-5 = "i"
note_steps-4 = "o"
note_steps-3 = "p"
chord_prev = "["
chord_next = "]"
chord_repeat = \N{reverse solidus}

note_steps-2 = a
note_steps-1 = s
note_key = d
note_steps+1 = f
note_steps+2 = g
note_steps+3 = h
note_steps+4 = j
note_steps+5 = k
note_steps+6 = l
# ??? = ";"
next = (^M,^J,\N{line feed},\N{carriage return},KEY_ENTER)

note_steps+7 = z
note_steps+8 = x
note_steps+9 = c
note_steps+10 = v
note_steps+11 = b
note_steps+12 = n
chord_3 = "m"
chord_2 = ","
chord_1 = "."
chord_0 = "/"

"""

config.read_string(default_config,"<default configuration>") 
home_dir = None

parser = argparse.ArgumentParser(
                    description="A stupidly simple music composition aid.")
def load_home_config(args = None):
    """ Load the user-specific configuration.

        It can not contain the `project` section. It is based upon the
        application's internal defaults. (Note: It will modified with project
        specific settings before it is used.)
    """
    global config
    global home_dir
    if home_dir is None:
        if args is not None and args.user_config is not None:
            home_dir = Path(args.user_config)
        else:
            home_dir = Path("~/.bittyband").expanduser()
        home_dir.mkdir(parents=True,exist_ok=True)
        home_config = home_dir / "settings.conf"
        if home_config.exists():
            config.read(home_config)
            if "project" in config:
                config["project"].clear()
    return config

class ConfigError(Exception):
    pass

def get_project_root():
    """ Return the common base-directory for projects.

        This allows you to specify a `--project` on the command-line
        and to reference a project directory off of this root without adding
        a mapping in the `projects` section of the user configuration file.

        The value for this comes from a `root` symlink in the `--user-config`
        directory. If this is a file, instead of a directory, it needs to
        be the name of the directory. (It does '~' expansion.)

        The expectation is that this will allow a common `~/BittyProjects`
        or `~/Documents/BittyTunes` directory to root your projects.
    """
    global home_dir
    root = home_dir / "root"
    if root.is_file():
        t = root.read_text().strip()
        root = Path(t).expanduser()
    if root.is_dir():
        return root.resolve()
    return None

def find_project_dir(project): 
    global project_dir
    if project_dir is None:
        if project is None:
            project = "."
        root = get_project_root()
        if "." == project:
            project_dir = Path(".")
        elif "/" not in project and "\\" not in project:
            if "projects" in config:
                project_dir = config["projects"].get(project)
                if project_dir is not None:
                    project_dir = Path(project_dir)
                else:
                    project_dir = Path(project)
        else:
            project_dir = Path(project)

        if project_dir is None:
            project_dir = Path(".", project)
        if root is None:
            project_dir = project_dir.expanduser()
        else:
            project_dir = root.joinpath(project_dir).expanduser()
        if project_dir.is_dir():
            project_dir = project_dir.resolve()
    return project_dir

def load_project_config(args = None):
    global project_dir
    global config

    load_home_config(args)
    project_dir = find_project_dir(args.project)
    conf_path = project_dir / "bittyband.conf"
    if not conf_path.exists():
        raise ConfigError("Project has no configuration file.")
    config.read(str(conf_path))
    if config["project"].getint("version") < 1:
        raise ConfigError("Project is an unsupported version.")
    if args.midiport is not None:
        config["project"]["midiport"] = args.midiport
    return config

project_stub = """
[project]
version = 1
"""

def create(args):
    global project_dir
    load_home_config(args)
    project_dir = find_project_dir(args.project)
    project_dir.mkdir(parents=True,exist_ok=True)
    conf_path = project_dir / "bittyband.conf"
    conf_path.write_text(project_stub)
    return True

parser.add_argument("--user-config", metavar="DIR", dest="user_config",
        help="Specify an alternate user configuration directory")
parser.add_argument("-p", "--project", metavar="PROJ",
        help="Specify a project or project location other than the current directory.")
parser.add_argument("--midiport", metavar="PORT",
        help="Specify an explicit MIDI port to use. (Default: first available.)")
# parser.add_argument("-u", "--user", help="ignore project-specific config file")
subparsers = parser.add_subparsers(title="Actions", help="Action to take")
parser_create = subparsers.add_parser("create", description="Create a new project")
parser_create.add_argument("project", help="Name of project directory to create.")
parser_create.set_defaults(func=create, mode="func")
parser_gui = subparsers.add_parser("gui", description="Start the GUI")
parser_gui.set_defaults(mode="gui")
parser_test = subparsers.add_parser("test", description="Perform some internal tests")
parser_test.set_defaults(mode="test")

