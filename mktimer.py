#!/usr/bin/env python3
"""Systemd timer setup"""

import argparse
from os import chdir
from os.path import dirname, expanduser, realpath
from pathlib import Path
from shlex import join
from shutil import copyfile, which
from subprocess import run
import sys
from sys import argv


def prun(cmd: list[str], check: bool = True) -> None:
    print("+", join(cmd))
    run(cmd, check=check)


def main():
    default_wd = dirname(argv[0])

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "working_dir",
        help="working dir, default=%(default)s",
        default=default_wd,
        nargs="?",
    )
    parser.add_argument("--uv", help="override uv path")
    args = parser.parse_args()

    if not (uv := args.uv):
        uv = which("uv")
        if not uv:
            sys.exit("Unable to locate 'uv' executable. Specify with --uv")
        uv = realpath(uv)

    chdir(dirname(argv[0]))
    with open("calsync.service") as fp:
        data = fp.read()

    wd = realpath(expanduser(args.working_dir))
    data = data.format(DIR=wd, UV=uv)

    basedir = Path(expanduser("~/.config/systemd/user"))
    with (basedir / "calsync.service").open("w") as fp:
        print("writing", fp.name)
        fp.write(data)

    for fn in ("calsync.timer", "calsync-failure@.service"):
        dest = basedir / fn
        print("copy", fn, "->", dest)
        copyfile(fn, dest)

    prun(["systemctl", "--user", "daemon-reload"])
    prun(["systemctl", "--user", "enable", "calsync.timer"])

    prun(["systemctl", "--user", "status", "calsync.timer"], check=False)

    print("-" * 65)
    print("setup complete.")
    print("To enable lingering so the timer runs even when you're not logged in, run:")
    print("sudo loginctl enable-linger $USER")


if __name__ == "__main__":
    main()
