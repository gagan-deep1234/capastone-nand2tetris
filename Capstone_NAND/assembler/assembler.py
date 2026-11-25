"""
Part B - Hack Assembler in Python
Nand to Tetris I (ETCCNT301) Capstone Project

Two-pass Hack assembler (.asm -> .hack):
  Pass 1: Remove comments and blank lines, record label addresses like (LOOP).
  Pass 2: Translate every A-instruction and C-instruction into 16-bit binary.
          New variables are assigned RAM addresses starting at 16.

Personal number K = last two digits of roll number (default K = 41).
K mod 3 extra feature:
  0 -> Save all labels and variables with their addresses in symbols.txt.
  1 -> Print a clear message with line number for invalid lines instead of crashing.
  2 -> Print a warning if the same label is defined twice.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Change DEFAULT_K to the last two digits of your roll number (0..99)
DEFAULT_K = 41

PREDEFINED_SYMBOLS: Dict[str, int] = {
    "SP": 0,
    "LCL": 1,
    "ARG": 2,
    "THIS": 3,
    "THAT": 4,
    **{f"R{i}": i for i in range(16)},
    "SCREEN": 16384,
    "KBD": 24576,
}

COMP_TABLE: Dict[str, str] = {
    # a = 0
    "0": "0101010",
    "1": "0111111",
    "-1": "0111010",
    "D": "0001100",
    "A": "0110000",
    "!D": "0001101",
    "!A": "0110001",
    "-D": "0001111",
    "-A": "0110011",
    "D+1": "0011111",
    "A+1": "0110111",
    "D-1": "0001110",
    "A-1": "0110010",
    "D+A": "0000010",
    "D-A": "0010011",
    "A-D": "0000111",
    "D&A": "0000000",
    "D|A": "0010101",
    # a = 1
    "M": "1110000",
    "!M": "1110001",
    "-M": "1110011",
    "M+1": "1110111",
    "M-1": "1110010",
    "D+M": "1000010",
    "D-M": "1010011",
    "M-D": "1000111",
    "D&M": "1000000",
    "D|M": "1010101",
}

DEST_TABLE: Dict[str, str] = {
    "": "000",
    "M": "001",
    "D": "010",
    "MD": "011",
    "A": "100",
    "AM": "101",
    "AD": "110",
    "AMD": "111",
}

JUMP_TABLE: Dict[str, str] = {
    "": "000",
    "JGT": "001",
    "JEQ": "010",
    "JGE": "011",
    "JLT": "100",
    "JNE": "101",
    "JLE": "110",
    "JMP": "111",
}

VALID_SYMBOL_RE = re.compile(r"^[A-Za-z_.$:][A-Za-z0-9_.$:]*$")


def strip_comment(line: str) -> str:
    """Remove '//' comments and surrounding whitespace."""
    idx = line.find("//")
    if idx != -1:
        line = line[:idx]
    return line.strip()


def is_valid_symbol(name: str) -> bool:
    """Return True if name is a valid Hack assembly symbol."""
    return bool(VALID_SYMBOL_RE.match(name))


def format_symbols_text(
    labels: Dict[str, int], variables: Dict[str, int]
) -> str:
    """Format user labels and variables cleanly for symbols.txt."""
    lines: List[str] = [
        "# Hack Assembler Symbol Table (Labels & Variables)",
        "",
        "[Labels (ROM Addresses)]",
    ]
    if labels:
        for name, addr in sorted(labels.items(), key=lambda kv: (kv[1], kv[0])):
            lines.append(f"{name} = {addr}")
    else:
        lines.append("(none)")

    lines.extend(["", "[Variables (RAM Addresses)]"])
    if variables:
        for name, addr in sorted(variables.items(), key=lambda kv: (kv[1], kv[0])):
            lines.append(f"{name} = {addr}")
    else:
        lines.append("(none)")

    return "\n".join(lines) + "\n"


def assemble_source(
    source: str,
    k: int = DEFAULT_K,
    symbols_path: Optional[Path] = None,
) -> Dict[str, object]:
    """
    Assemble Hack assembly source text into 16-bit binary strings.

    Returns a dictionary containing:
      - ok: bool
      - machine_code: list[str] (each 16-bit '0'/'1' string)
      - errors: list[str]
      - warnings: list[str]
      - labels: dict[str, int]
      - variables: dict[str, int]
      - symbols_text: str
      - k: int
      - k_mod_3: int
    """
    k_mod_3 = k % 3
    symbol_table: Dict[str, int] = dict(PREDEFINED_SYMBOLS)
    labels: Dict[str, int] = {}
    label_lines: Dict[str, int] = {}
    variables: Dict[str, int] = {}
    errors: List[str] = []
    warnings: List[str] = []

    # ------------------------------------------------------------------
    # Pass 1: Strip comments/blank lines and build label -> ROM address map
    # ------------------------------------------------------------------
    cleaned_instructions: List[Tuple[int, str]] = []
    rom_address = 0

    for line_no, raw_line in enumerate(source.splitlines(), start=1):
        cleaned = strip_comment(raw_line)
        if not cleaned:
            continue

        if cleaned.startswith("("):
            if not cleaned.endswith(")"):
                errors.append(f"Line {line_no}: invalid instruction '{cleaned}' (missing closing ')')")
                continue
            label_name = cleaned[1:-1].strip()
            if not label_name or not is_valid_symbol(label_name):
                errors.append(f"Line {line_no}: invalid label '{cleaned}'")
                continue

            if label_name in label_lines:
                if k_mod_3 == 2:
                    warnings.append(
                        f"Warning: Line {line_no}: duplicate label '({label_name})' "
                        f"(previously defined at line {label_lines[label_name]})"
                    )
                # Keep first definition if duplicated
                continue

            if label_name in PREDEFINED_SYMBOLS and k_mod_3 == 2:
                warnings.append(
                    f"Warning: Line {line_no}: label '({label_name})' shadows predefined symbol"
                )

            label_lines[label_name] = line_no
            labels[label_name] = rom_address
            symbol_table[label_name] = rom_address
        else:
            cleaned_instructions.append((line_no, cleaned))
            rom_address += 1

    # ------------------------------------------------------------------
    # Pass 2: Translate instructions and allocate RAM variables from 16
    # ------------------------------------------------------------------
    machine_code: List[str] = []
    next_var_address = 16

    for line_no, inst in cleaned_instructions:
        if inst.startswith("@"):
            symbol = inst[1:]
            if not symbol or any(ch.isspace() for ch in symbol):
                errors.append(f"Line {line_no}: invalid instruction '{inst}'")
                continue

            if symbol.isdigit():
                value = int(symbol)
                if value < 0 or value > 32767:
                    errors.append(
                        f"Line {line_no}: invalid instruction '{inst}' (address {value} out of 0..32767)"
                    )
                    continue
                machine_code.append(f"0{value:015b}")
            else:
                if not is_valid_symbol(symbol):
                    errors.append(f"Line {line_no}: invalid instruction '{inst}'")
                    continue
                if symbol not in symbol_table:
                    symbol_table[symbol] = next_var_address
                    variables[symbol] = next_var_address
                    next_var_address += 1
                addr = symbol_table[symbol]
                machine_code.append(f"0{addr:015b}")
        else:
            # C-instruction: [dest=]comp[;jump]
            compact = "".join(inst.split())
            dest_part = ""
            jump_part = ""
            comp_part = compact

            if "=" in comp_part:
                parts = comp_part.split("=")
                if len(parts) != 2 or not parts[0]:
                    errors.append(f"Line {line_no}: invalid instruction '{inst}'")
                    continue
                dest_part, comp_part = parts

            if ";" in comp_part:
                parts = comp_part.split(";")
                if len(parts) != 2 or not parts[1]:
                    errors.append(f"Line {line_no}: invalid instruction '{inst}'")
                    continue
                comp_part, jump_part = parts

            if dest_part not in DEST_TABLE or comp_part not in COMP_TABLE or jump_part not in JUMP_TABLE:
                errors.append(f"Line {line_no}: invalid instruction '{inst}'")
                continue

            bits = "111" + COMP_TABLE[comp_part] + DEST_TABLE[dest_part] + JUMP_TABLE[jump_part]
            machine_code.append(bits)

    symbols_text = format_symbols_text(labels, variables)
    if k_mod_3 == 0 and symbols_path is not None and not errors:
        symbols_path.write_text(symbols_text, encoding="utf-8")

    return {
        "ok": len(errors) == 0,
        "machine_code": machine_code,
        "errors": errors,
        "warnings": warnings,
        "labels": labels,
        "variables": variables,
        "symbols_text": symbols_text,
        "k": k,
        "k_mod_3": k_mod_3,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Hack Assembler (.asm -> .hack) for Nand to Tetris Capstone."
    )
    parser.add_argument("input", type=Path, help="Path to input .asm file")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Path to output .hack file (defaults to <input>.hack)",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=DEFAULT_K,
        help=f"Personal number K (last 2 digits of roll number, default={DEFAULT_K})",
    )
    args = parser.parse_args(argv)

    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        return 1

    out_path = args.out if args.out is not None else args.input.with_suffix(".hack")
    symbols_path = out_path.parent / "symbols.txt"

    source = args.input.read_text(encoding="utf-8")
    result = assemble_source(source, k=args.k, symbols_path=symbols_path)

    for warning in result["warnings"]:  # type: ignore[union-attr]
        print(warning, file=sys.stderr)

    if not result["ok"]:
        for err in result["errors"]:  # type: ignore[union-attr]
            print(err, file=sys.stderr)
        return 1

    out_path.write_text("\n".join(result["machine_code"]) + "\n", encoding="utf-8")  # type: ignore[arg-type]
    print(f"Assembled {args.input.name} -> {out_path} ({len(result['machine_code'])} instructions)")  # type: ignore[arg-type]
    if (args.k % 3) == 0:
        print(f"Saved labels and variables -> {symbols_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
