"""
Helper to generate Part C Box.asm for any personal number K (0..99).
Usage:
    python asm/generate_box.py 41
"""

from __future__ import annotations

import argparse
from pathlib import Path

SCREEN_BASE = 16384
WORDS_PER_ROW = 32
BOX_HEIGHT = 20


def build_box_asm(k: int) -> str:
    """Return Hack assembly source for Box.asm tailored to personal number k."""
    if k < 0 or k > 235:
        raise ValueError(f"K={k} puts the 20-row box outside the 256-row Hack screen.")
    words_wide = (k % 4) + 1
    pixels_wide = 16 * words_wide
    start_addr = SCREEN_BASE + WORDS_PER_ROW * k

    return f"""// Part C - Box.asm
// Nand to Tetris I (ETCCNT301) Capstone Project
// Draws a black box while any key is pressed; clears it when released.
//
// Generated for Personal Number K = {k}:
//   Start row   = K = {k}
//   Height      = {BOX_HEIGHT} rows (rows {k}..{k + BOX_HEIGHT - 1})
//   Width       = 16 * ((K mod 4) + 1) = 16 * {words_wide} = {pixels_wide} pixels ({words_wide} words per row)
//   Start addr  = SCREEN + 32 * {k} = {SCREEN_BASE} + {WORDS_PER_ROW * k} = {start_addr}

(LOOP)
    @KBD
    D=M
    @WHITE
    D;JEQ           // If no key pressed (KBD == 0), draw white (0)

    @color
    M=-1            // Key pressed -> black (-1 = 0xFFFF = 16 black pixels)
    @DRAW
    0;JMP

(WHITE)
    @color
    M=0             // Key released -> white (0 = 0x0000 = 16 white pixels)

(DRAW)
    @{start_addr}          // Start address = SCREEN ({SCREEN_BASE}) + 32 * {k}
    D=A
    @rowPtr
    M=D

    @{BOX_HEIGHT}             // Box height = {BOX_HEIGHT} rows
    D=A
    @rowCount
    M=D

(ROW_LOOP)
    @rowCount
    D=M
    @LOOP
    D;JEQ           // Finished all {BOX_HEIGHT} rows -> poll keyboard again

    @rowPtr
    D=M
    @addr
    M=D             // addr = start of current row

    @{words_wide}              // Width in words = ({k} mod 4) + 1 = {words_wide} words ({pixels_wide} pixels)
    D=A
    @colCount
    M=D

(COL_LOOP)
    @colCount
    D=M
    @NEXT_ROW
    D;JEQ           // Finished all words in this row

    @color
    D=M
    @addr
    A=M
    M=D             // Write 16 pixels (-1 black or 0 white) to Screen RAM

    @addr
    M=M+1           // Move to next 16-pixel word in the same row
    @colCount
    M=M-1
    @COL_LOOP
    0;JMP

(NEXT_ROW)
    @{WORDS_PER_ROW}
    D=A
    @rowPtr
    M=D+M           // Advance to next screen row (+32 words)

    @rowCount
    M=M-1
    @ROW_LOOP
    0;JMP
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Box.asm for a given K.")
    parser.add_argument("k", type=int, help="Personal number K (last 2 digits of roll number)")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).with_name("Box.asm"),
        help="Output path (default: asm/Box.asm)",
    )
    args = parser.parse_args()
    args.out.write_text(build_box_asm(args.k), encoding="utf-8")
    print(f"Generated {args.out} for K={args.k}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
