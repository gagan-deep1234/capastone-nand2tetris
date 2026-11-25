"""
Hack Computer Emulator (16-bit CPU + 24K Memory + 512x256 Screen + Keyboard).
Executes 16-bit binary .hack machine code produced by assembler.py.
"""

from __future__ import annotations

from typing import Dict, List

SCREEN_START = 16384
SCREEN_WORDS = 8192  # 256 rows * 32 words/row
KBD_ADDR = 24576
TOTAL_MEMORY = 24577


def to_signed16(val: int) -> int:
    """Convert unsigned 16-bit integer (0..65535) to signed (-32768..32767)."""
    val &= 0xFFFF
    return val - 0x10000 if (val & 0x8000) else val


class HackComputer:
    """Cycle-accurate behavioral emulator of the Hack Computer."""

    def __init__(self) -> None:
        self.rom: List[int] = []
        self.ram: List[int] = [0] * TOTAL_MEMORY
        self.a: int = 0
        self.d: int = 0
        self.pc: int = 0
        self.cycles: int = 0

    def reset_cpu(self) -> None:
        """Reset registers and cycle count while keeping ROM/RAM intact."""
        self.a = 0
        self.d = 0
        self.pc = 0
        self.cycles = 0

    def hard_reset(self) -> None:
        """Clear RAM and reset CPU registers."""
        self.ram = [0] * TOTAL_MEMORY
        self.reset_cpu()

    def load_program(
        self, machine_code: List[str], ram_init: Dict[int, int] | None = None
    ) -> None:
        """Load 16-bit binary instruction strings into ROM32K and reset."""
        self.rom = [int(bits, 2) & 0xFFFF for bits in machine_code]
        self.hard_reset()
        if ram_init:
            for addr, val in ram_init.items():
                if 0 <= addr < KBD_ADDR:
                    self.ram[addr] = val & 0xFFFF

    def set_key(self, key_code: int) -> None:
        """Set memory-mapped keyboard register RAM[24576]."""
        self.ram[KBD_ADDR] = key_code & 0xFFFF

    def step_one(self) -> None:
        """Execute a single Hack CPU instruction cycle."""
        if self.pc < 0 or self.pc >= len(self.rom):
            # Halted / out of ROM bounds: keep PC steady
            self.cycles += 1
            return

        inst = self.rom[self.pc]
        self.cycles += 1

        if (inst & 0x8000) == 0:
            # A-instruction: 0vvvvvvvvvvvvvvv
            self.a = inst & 0x7FFF
            self.pc = (self.pc + 1) & 0x7FFF
            return

        # C-instruction: 111 a c1 c2 c3 c4 c5 c6 d1 d2 d3 j1 j2 j3
        a_bit = (inst >> 12) & 1
        zx = (inst >> 11) & 1
        nx = (inst >> 10) & 1
        zy = (inst >> 9) & 1
        ny = (inst >> 8) & 1
        f_bit = (inst >> 7) & 1
        no = (inst >> 6) & 1

        d1 = (inst >> 5) & 1  # A
        d2 = (inst >> 4) & 1  # D
        d3 = (inst >> 3) & 1  # M

        j1 = (inst >> 2) & 1  # < 0
        j2 = (inst >> 1) & 1  # == 0
        j3 = inst & 1         # > 0

        # Read M before potential A modification
        addr_m = self.a & 0x7FFF
        m_val = self.ram[addr_m] if addr_m < TOTAL_MEMORY else 0

        x = self.d
        y = m_val if a_bit else self.a

        if zx:
            x = 0
        if nx:
            x = (~x) & 0xFFFF
        if zy:
            y = 0
        if ny:
            y = (~y) & 0xFFFF

        out = ((x + y) & 0xFFFF) if f_bit else ((x & y) & 0xFFFF)
        if no:
            out = (~out) & 0xFFFF

        signed_out = to_signed16(out)

        # Write destinations (note M uses previous A, standard Hack semantics)
        if d3 and addr_m < KBD_ADDR:
            self.ram[addr_m] = out
        if d1:
            self.a = out & 0xFFFF
        if d2:
            self.d = out & 0xFFFF

        # Jump logic
        jump = (
            (j1 and signed_out < 0)
            or (j2 and signed_out == 0)
            or (j3 and signed_out > 0)
        )
        if jump:
            self.pc = self.a & 0x7FFF
        else:
            self.pc = (self.pc + 1) & 0x7FFF

    def run(self, cycles: int) -> None:
        """Execute up to `cycles` CPU steps."""
        for _ in range(max(0, cycles)):
            self.step_one()

    def snapshot(self) -> Dict[str, object]:
        """Return CPU state, first 24 RAM words, and non-zero screen words."""
        screen_non_zero: Dict[str, int] = {}
        for offset in range(SCREEN_WORDS):
            val = self.ram[SCREEN_START + offset]
            if val != 0:
                screen_non_zero[str(offset)] = val

        ram_preview = {
            str(addr): to_signed16(self.ram[addr]) for addr in range(24)
        }
        return {
            "a": to_signed16(self.a),
            "a_unsigned": self.a,
            "d": to_signed16(self.d),
            "pc": self.pc,
            "kbd": self.ram[KBD_ADDR],
            "cycles": self.cycles,
            "rom_size": len(self.rom),
            "ram_preview": ram_preview,
            "screen_non_zero": screen_non_zero,
        }
