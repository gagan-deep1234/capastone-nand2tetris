"""
Automated verification tests for the Nand to Tetris Capstone project:
  - Part B Assembler (two-pass translation, K mod 3 features)
  - Part C Box.asm + Hack Computer emulator (keypress/release & geometry)
  - Backend HTTP endpoints & static frontend serving
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from asm.generate_box import build_box_asm  # noqa: E402
from assembler.assembler import assemble_source  # noqa: E402
from backend.hack_cpu import SCREEN_START, SCREEN_WORDS, HackComputer  # noqa: E402
from backend.server import CapstoneHandler  # noqa: E402


class _FakeSocket:
    def __init__(self, raw_request: bytes) -> None:
        self._rfile = io.BytesIO(raw_request)
        self._wfile = io.BytesIO()

    def makefile(self, mode: str, *args: Any, **kwargs: Any) -> Any:
        return self._rfile if "r" in mode else self._wfile

    def sendall(self, data: bytes) -> None:
        self._wfile.write(data)

    def close(self) -> None:
        pass


def _invoke_handler(
    method: str, path: str, body: Dict[str, Any] | None = None
) -> tuple[int, bytes]:
    payload = json.dumps(body).encode("utf-8") if body is not None else b""
    headers = f"{method} {path} HTTP/1.1\r\nHost: localhost\r\n"
    if body is not None:
        headers += f"Content-Type: application/json\r\nContent-Length: {len(payload)}\r\n"
    headers += "\r\n"
    sock = _FakeSocket(headers.encode("utf-8") + payload)
    CapstoneHandler(sock, ("127.0.0.1", 0), None)  # type: ignore[arg-type]
    raw_resp = sock._wfile.getvalue()
    head, _, resp_body = raw_resp.partition(b"\r\n\r\n")
    status_code = int(head.splitlines()[0].split()[1])
    return status_code, resp_body


class TestAssemblerAndBox(unittest.TestCase):
    def test_add_asm_exact_binary(self) -> None:
        src = (ROOT_DIR / "assembler" / "samples" / "Add.asm").read_text(encoding="utf-8")
        res = assemble_source(src, k=41)
        self.assertTrue(res["ok"])
        expected = [
            "0000000000000010",  # @2
            "1110110000010000",  # D=A
            "0000000000000011",  # @3
            "1110000010010000",  # D=D+A
            "0000000000000000",  # @0
            "1110001100001000",  # M=D
        ]
        self.assertEqual(res["machine_code"], expected)

        cpu = HackComputer()
        cpu.load_program(res["machine_code"])
        cpu.run(10)
        self.assertEqual(cpu.ram[0], 5)

    def test_max_asm_execution(self) -> None:
        src = (ROOT_DIR / "assembler" / "samples" / "Max.asm").read_text(encoding="utf-8")
        res = assemble_source(src, k=41)
        self.assertTrue(res["ok"])

        cpu = HackComputer()
        cpu.load_program(res["machine_code"], ram_init={0: 17, 1: 42})
        cpu.run(50)
        self.assertEqual(cpu.ram[2], 42)

        cpu.load_program(res["machine_code"], ram_init={0: 99, 1: 12})
        cpu.run(50)
        self.assertEqual(cpu.ram[2], 99)

    def test_rect_asm_execution(self) -> None:
        src = (ROOT_DIR / "assembler" / "samples" / "Rect.asm").read_text(encoding="utf-8")
        res = assemble_source(src, k=41)
        self.assertTrue(res["ok"])

        cpu = HackComputer()
        cpu.load_program(res["machine_code"], ram_init={0: 4})
        cpu.run(200)
        for row in range(4):
            self.assertEqual(cpu.ram[SCREEN_START + 32 * row], 0xFFFF)
        self.assertEqual(cpu.ram[SCREEN_START + 32 * 4], 0)

    def test_k_mod_3_features(self) -> None:
        # K mod 3 == 0: writes symbols.txt
        with tempfile.TemporaryDirectory() as tmp:
            sym_file = Path(tmp) / "symbols.txt"
            res0 = assemble_source("(LOOP)\n@counter\nM=M+1\n@LOOP\n0;JMP\n", k=42, symbols_path=sym_file)
            self.assertTrue(res0["ok"])
            self.assertTrue(sym_file.is_file())
            sym_text = sym_file.read_text(encoding="utf-8")
            self.assertIn("LOOP = 0", sym_text)
            self.assertIn("counter = 16", sym_text)

        # K mod 3 == 1: clear line-numbered error on bad line
        res1 = assemble_source("@2\nD=A\nINVALID_OP\n@0\nM=D\n", k=40)
        self.assertFalse(res1["ok"])
        self.assertTrue(any("Line 3:" in err for err in res1["errors"]))

        # K mod 3 == 2: warning when same label written twice
        res2 = assemble_source("(LOOP)\n@0\n(LOOP)\n0;JMP\n", k=41)
        self.assertTrue(res2["ok"])
        self.assertTrue(any("duplicate label '(LOOP)'" in w for w in res2["warnings"]))

    def test_box_asm_geometry_and_keypress(self) -> None:
        for k in (0, 41, 42, 43):
            box_src = build_box_asm(k)
            if k == 41:
                self.assertEqual(
                    box_src,
                    (ROOT_DIR / "asm" / "Box.asm").read_text(encoding="utf-8"),
                )
            res = assemble_source(box_src, k=k)
            self.assertTrue(res["ok"], f"Box.asm failed to assemble for K={k}: {res['errors']}")

            cpu = HackComputer()
            cpu.load_program(res["machine_code"])

            words_wide = (k % 4) + 1
            expected_offsets = {
                32 * r + c for r in range(k, k + 20) for c in range(words_wide)
            }

            # Press key -> black box appears at exact coordinates
            cpu.set_key(65)
            cpu.run(5000)
            active_offsets = {
                off for off in range(SCREEN_WORDS) if cpu.ram[SCREEN_START + off] == 0xFFFF
            }
            self.assertEqual(active_offsets, expected_offsets, f"Mismatch for K={k}")

            # Release key -> box disappears completely
            cpu.set_key(0)
            cpu.run(5000)
            remaining = [
                off for off in range(SCREEN_WORDS) if cpu.ram[SCREEN_START + off] != 0
            ]
            self.assertEqual(remaining, [], f"Screen not cleared on key release for K={k}")

    def test_http_server_endpoints(self) -> None:
        status, html_bytes = _invoke_handler("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("Make the Computer Draw a Box", html_bytes.decode("utf-8"))

        status, files_bytes = _invoke_handler("GET", "/api/files")
        self.assertEqual(status, 200)
        files_data = json.loads(files_bytes.decode("utf-8"))
        self.assertIn("CPU.hdl", files_data["hdl"])
        self.assertIn("Memory.hdl", files_data["hdl"])
        self.assertIn("Computer.hdl", files_data["hdl"])
        self.assertIn("Box.asm", files_data["samples"])

        status, asm_bytes = _invoke_handler(
            "POST", "/api/assemble", {"source": build_box_asm(41), "k": 41}
        )
        self.assertEqual(status, 200)
        asm_res = json.loads(asm_bytes.decode("utf-8"))
        self.assertTrue(asm_res["ok"])

        status, load_bytes = _invoke_handler(
            "POST", "/api/sim/load", {"machine_code": asm_res["machine_code"]}
        )
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(load_bytes.decode("utf-8"))["ok"])

        status, step_bytes = _invoke_handler(
            "POST", "/api/sim/step", {"cycles": 5000, "key_code": 65}
        )
        self.assertEqual(status, 200)
        step_res = json.loads(step_bytes.decode("utf-8"))
        self.assertTrue(step_res["ok"])
        self.assertEqual(len(step_res["screen_non_zero"]), 40)


if __name__ == "__main__":
    unittest.main(verbosity=2)
