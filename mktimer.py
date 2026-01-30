#!/usr/bin/env python3
"""Systemd timer setup"""

import argparse
from os import chdir, getcwd
from subprocess import run
from os.path import dirname, expanduser, realpath
from pathlib import Path
from sys import argv
from shutil import copyfile

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("venv", help="virtual env dir", action='store', nargs=1)
    parser.add_argument("working_dir", help="working dir, default=script dir", nargs='?')
    args = parser.parse_args()

    chdir(dirname(argv[0]))
    with open("calsync.service", "r") as fp:
        data = fp.read()

    venv = realpath(expanduser(args.venv[0]))
    wd = realpath(expanduser(args.working_dir) if args.working_dir else dirname(argv[0]))
    data = data.format(VENV=venv, DIR=wd)

    basedir = Path(expanduser("~/.config/systemd/user"))
    with (basedir / "calsync.service").open("w") as fp:
        fp.write(data)
    
    for fn in ("calsync.timer", "calsync-failure@.service"):
        copyfile(fn, basedir/fn)
    
    run(["systemctl", "--user", "daemon-reload"], check=True)
    run(["systemctl", "--user", "enable", "calsync.timer"], check=True)

    print("# Enable lingering so the timer runs even when you're not logged in")
    print("sudo loginctl enable-linger $USER")

    run(["systemctl", "--user", "status", "calsync.timer"], check=True)




if __name__ == '__main__':
    main()

