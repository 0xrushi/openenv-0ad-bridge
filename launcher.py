# -*- coding: utf-8 -*-

"""Minimal 0 A.D. launcher for RL-interface control.

This repo no longer ships a 0 A.D. AI/mod. The purpose of this launcher is to
start 0 A.D. with the built-in RL interface HTTP server enabled.

Environment variables:
- ZEROAD_RL_INTERFACE: address for 0 A.D. `--rl-interface`
  Example: ZEROAD_RL_INTERFACE=127.0.0.1:6000

Examples:
  ZEROAD_RL_INTERFACE=127.0.0.1:6000 python launcher.py
  python launcher.py --map="scenarios/arcadia" --players=2
"""

from __future__ import annotations

import argparse
import os
import subprocess
from typing import List


def build_cmd(
    binary: str, map_name: str, players: int, xres: int, yres: int
) -> List[str]:
    cmd: List[str] = [
        binary,
        "-quickstart",
        f"-autostart={map_name}",
        "-mod=public",
        f"-autostart-players={players}",
        f"-xres={xres}",
        f"-yres={yres}",
    ]

    rl_addr = os.environ.get("ZEROAD_RL_INTERFACE")
    if rl_addr:
        cmd.append(f"--rl-interface={rl_addr}")

    return cmd


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Launch 0 A.D. with RL interface enabled"
    )
    parser.add_argument(
        "--binary", default="/usr/bin/0ad", help="Path to 0 A.D. binary"
    )
    parser.add_argument(
        "--map",
        default="scenarios/arcadia",
        help="Autostart map (e.g. scenarios/arcadia, random/anatolian_plateau)",
    )
    parser.add_argument("--players", type=int, default=2, help="Number of players")
    parser.add_argument("--xres", type=int, default=1276, help="Window width")
    parser.add_argument("--yres", type=int, default=768, help="Window height")
    args = parser.parse_args()

    cmd = build_cmd(args.binary, args.map, args.players, args.xres, args.yres)
    print("cmd:", " ".join(cmd))
    subprocess.run(cmd, check=False)


if __name__ == "__main__":
    main()
