"""
Python Backend Server for the Nand to Tetris Capstone Web App.
Serves the REST API (assembler, Box.asm generator, Hack CPU simulator, HDL viewer)
and static frontend files using only Python's standard library.

Run:
    python backend/server.py --port 8000
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from asm.generate_box import build_box_asm  # noqa: E402
from assembler.assembler import DEFAULT_K, assemble_source  # noqa: E402
from backend.hack_cpu import HackComputer  # noqa: E402

FRONTEND_DIR = ROOT_DIR / "frontend"
HDL_DIR = ROOT_DIR / "hdl"
SAMPLES_DIR = ROOT_DIR / "assembler" / "samples"
BOX_ASM_PATH = ROOT_DIR / "asm" / "Box.asm"

CPU_LOCK = threading.Lock()
CPU = HackComputer()


def feature_description(k: int) -> str:
    mod = k % 3
    if mod == 0:
        return "K mod 3 = 0: Save all labels and variables with their addresses in symbols.txt"
    if mod == 1:
        return "K mod 3 = 1: Print clear line-numbered errors instead of crashing"
    return "K mod 3 = 2: Print a warning if the same label is defined twice"


def box_geometry(k: int) -> Dict[str, Any]:
    words_wide = (k % 4) + 1
    pixels_wide = 16 * words_wide
    start_addr = 16384 + 32 * k
    return {
        "k": k,
        "k_mod_3": k % 3,
        "k_mod_4": k % 4,
        "extra_feature": feature_description(k),
        "start_row": k,
        "height_rows": 20,
        "width_words": words_wide,
        "width_pixels": pixels_wide,
        "start_addr": start_addr,
    }


class CapstoneHandler(BaseHTTPRequestHandler):
    server_version = "HackCapstoneServer/1.0"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        # Keep terminal logs concise
        pass

    def _send_json(self, payload: Dict[str, Any], status: int = HTTPStatus.OK) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        return json.loads(raw.decode("utf-8"))

    def _serve_static(self, rel_path: str) -> None:
        clean = rel_path.lstrip("/") or "index.html"
        target = (FRONTEND_DIR / clean).resolve()
        if not str(target).startswith(str(FRONTEND_DIR.resolve())) or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return
        ctype, _ = mimetypes.guess_type(str(target))
        content = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]

        if path == "/api/health":
            self._send_json({"status": "ok", "default_k": DEFAULT_K})
            return

        if path == "/api/files":
            hdl_files = {}
            for name in ("CPU.hdl", "Memory.hdl", "Computer.hdl"):
                p = HDL_DIR / name
                if p.is_file():
                    hdl_files[name] = p.read_text(encoding="utf-8")

            sample_files = {}
            if BOX_ASM_PATH.is_file():
                sample_files["Box.asm"] = BOX_ASM_PATH.read_text(encoding="utf-8")
            for p in sorted(SAMPLES_DIR.glob("*.asm")):
                sample_files[p.name] = p.read_text(encoding="utf-8")

            self._send_json({"hdl": hdl_files, "samples": sample_files})
            return

        if path == "/api/sim/state":
            with CPU_LOCK:
                self._send_json({"ok": True, **CPU.snapshot()})
            return

        self._serve_static(path)

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        try:
            body = self._read_json()
        except json.JSONDecodeError:
            self._send_json({"ok": False, "error": "Invalid JSON body"}, HTTPStatus.BAD_REQUEST)
            return

        if path == "/api/box/generate":
            try:
                k = int(body.get("k", DEFAULT_K))
                source = build_box_asm(k)
            except (TypeError, ValueError) as exc:
                self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            self._send_json({"ok": True, "source": source, "geometry": box_geometry(k)})
            return

        if path == "/api/assemble":
            source = str(body.get("source", ""))
            try:
                k = int(body.get("k", DEFAULT_K))
            except (TypeError, ValueError):
                k = DEFAULT_K
            save_symbols = bool(body.get("save_symbols", False))
            symbols_path = (ROOT_DIR / "assembler" / "symbols.txt") if save_symbols else None
            res = assemble_source(source, k=k, symbols_path=symbols_path)
            res["feature_description"] = feature_description(k)
            self._send_json(res)
            return

        if path == "/api/sim/load":
            machine_code = body.get("machine_code", [])
            if not isinstance(machine_code, list):
                self._send_json({"ok": False, "error": "machine_code must be a list"}, HTTPStatus.BAD_REQUEST)
                return
            raw_ram = body.get("ram_init", {}) or {}
            ram_init = {int(k): int(v) for k, v in raw_ram.items()}
            with CPU_LOCK:
                CPU.load_program([str(x) for x in machine_code], ram_init=ram_init)
                snap = CPU.snapshot()
            self._send_json({"ok": True, **snap})
            return

        if path == "/api/sim/step":
            cycles = min(max(int(body.get("cycles", 1)), 0), 50000)
            key_code = int(body.get("key_code", 0))
            with CPU_LOCK:
                CPU.set_key(key_code)
                CPU.run(cycles)
                snap = CPU.snapshot()
            self._send_json({"ok": True, **snap})
            return

        if path == "/api/sim/reset":
            with CPU_LOCK:
                CPU.hard_reset()
                snap = CPU.snapshot()
            self._send_json({"ok": True, **snap})
            return

        self._send_json({"ok": False, "error": f"Unknown endpoint: {path}"}, HTTPStatus.NOT_FOUND)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Hack Capstone Backend Server.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), CapstoneHandler)
    print(f"Hack Capstone Server running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.server_close()


if __name__ == "__main__":
    main()
