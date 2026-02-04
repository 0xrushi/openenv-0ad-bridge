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
import shutil
import subprocess
from typing import List


def _parse_mod_list(value: str) -> List[str]:
    # Accept comma- or whitespace-separated lists.
    mods: List[str] = []
    for part in value.replace(",", " ").split():
        m = part.strip()
        if m:
            mods.append(m)
    return mods


def _mod_exists(mod_name: str) -> bool:
    # Common 0 A.D. mod search paths.
    for base in (
        "/usr/share/games/0ad/mods",
        os.path.expanduser("~/.local/share/0ad/mods"),
    ):
        if os.path.isdir(os.path.join(base, mod_name)):
            return True
    return False


def build_cmd(
    binary: str,
    map_name: str,
    players: int,
    xres: int,
    yres: int,
    civ: str | None,
) -> List[str]:
    # Civilization selection:
    # For a deterministic civ, prefer civ-specific sandbox scenarios.
    # (Many scenario maps, e.g. scenarios/arcadia, hardcode player civs.)
    if civ:
        normalized = civ.strip().lower()
        if normalized in {"athens", "athenians"}:
            normalized = "athen"
        if normalized == "athen":
            map_name = "scenarios/arcadia"

    cmd: List[str] = [
        binary,
        "-quickstart",
        f"-autostart={map_name}",
        f"-autostart-players={players}",
        f"-xres={xres}",
        f"-yres={yres}",
    ]

    # Base mod(s).
    cmd.append("-mod=public")

    # Auto-enable local fixes when present.
    if os.environ.get("ZEROAD_DISABLE_OPENENV_FIX") != "1" and _mod_exists(
        "openenv_fix"
    ):
        cmd.append("-mod=openenv_fix")

    extra_mods = os.environ.get("ZEROAD_MODS")
    if extra_mods:
        for mod in _parse_mod_list(extra_mods):
            cmd.append(f"-mod={mod}")

    rl_addr = os.environ.get("ZEROAD_RL_INTERFACE")
    if rl_addr:
        cmd.append(f"--rl-interface={rl_addr}")

    # Useful in containers/CI where audio devices aren't present.
    if os.environ.get("ZEROAD_NOSOUND") == "1":
        cmd.append("-nosound")

    return cmd


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Launch 0 A.D. with RL interface enabled"
    )
    parser.add_argument(
        "--binary",
        default=os.environ.get("ZEROAD_BINARY") or "pyrogenesis",
        help="Path to 0 A.D. binary (or '0ad' if on PATH)",
    )
    parser.add_argument(
        "--map",
        default="scenarios/arcadia",
        help="Autostart map (e.g. scenarios/arcadia, random/anatolian_plateau)",
    )
    parser.add_argument(
        "--civ",
        default=os.environ.get("ZEROAD_CIV", "athen"),
        help="Force a civilization by selecting a civ-specific sandbox scenario (e.g. athen).",
    )
    parser.add_argument("--players", type=int, default=2, help="Number of players")
    parser.add_argument("--xres", type=int, default=1276, help="Window width")
    parser.add_argument("--yres", type=int, default=768, help="Window height")
    parser.add_argument(
        "--nosound",
        action="store_true",
        help="Disable audio (-nosound). Also sets ZEROAD_NOSOUND=1 for consistency.",
    )
    args = parser.parse_args()

    if args.nosound:
        os.environ["ZEROAD_NOSOUND"] = "1"

    # Resolve binary across common distro/container layouts.
    resolved = args.binary
    if "/" in resolved:
        if not os.path.exists(resolved):
            resolved = ""
    else:
        resolved = shutil.which(resolved) or ""

    if not resolved:
        for candidate in [
            "/usr/bin/pyrogenesis",
            "/usr/games/pyrogenesis",
            "/usr/bin/0ad",
            "/usr/games/0ad",
            "pyrogenesis",
            "0ad",
        ]:
            if "/" in candidate:
                if os.path.exists(candidate):
                    resolved = candidate
                    break
            else:
                found = shutil.which(candidate)
                if found:
                    resolved = found
                    break

    if not resolved:
        resolved = args.binary

    cmd = build_cmd(resolved, args.map, args.players, args.xres, args.yres, args.civ)
    print("cmd:", " ".join(cmd))
    subprocess.run(cmd, check=False)


if __name__ == "__main__":
    main()
