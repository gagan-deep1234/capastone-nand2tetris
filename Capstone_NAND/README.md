# Hack Computer Capstone Studio — Nand to Tetris I (ETCCNT301)

Complete codebase for **Make the Computer Draw a Box** (Parts A, B, C) plus an interactive **Python Backend + Web Frontend** Hack Computer & Screen Simulator.

## Project Structure

- **`hdl/` (Part A — Hardware Description Language)**
  - `hdl/CPU.hdl` — 16-bit Hack CPU (`ARegister`, `DRegister`, `ALU`, `PC`, jump logic)
  - `hdl/Memory.hdl` — 24K Data Memory (`RAM16K` + `Screen` + `Keyboard`)
  - `hdl/Computer.hdl` — Top-level Hack Computer (`ROM32K` + `CPU` + `Memory`)
  - `hdl/chips/` — Supporting lab chips (`ALU.hdl`, `PC.hdl`, `Register.hdl`, `Bit.hdl`)
- **`assembler/` (Part B — Python Hack Assembler)**
  - `assembler/assembler.py` — Two-pass `.asm` → `.hack` assembler supporting `K mod 3` features (`0`: `symbols.txt`, `1`: line-numbered errors, `2`: duplicate label warnings)
  - `assembler/samples/` — `Add.asm`, `Max.asm`, `Rect.asm`
- **`asm/` (Part C — Box Program)**
  - `asm/Box.asm` — Draws a black box on keypress and clears it on release (default `K = 41`)
  - `asm/generate_box.py` — Generates `asm/Box.asm` for your personal 2-digit `K`
- **`backend/` (Python Backend & Hack CPU Emulator)**
  - `backend/hack_cpu.py` — Cycle-accurate 16-bit Hack Computer emulator
  - `backend/server.py` — Standard-library HTTP API + static file server
- **`frontend/` (Interactive Web UI)**
  - `frontend/index.html`, `frontend/styles.css`, `frontend/app.js` — Live 512×256 Hack display, keyboard hold simulation, Part B assembler workbench, and Part A HDL viewer
- **`tests/test_capstone.py`** — Automated tests for all parts

## Quick Start

### 1. Set your personal number `K` (last 2 digits of roll number)
```bash
python asm/generate_box.py 41
python assembler/assembler.py asm/Box.asm --k 41 --out asm/Box.hack
```

### 2. Run the Full-Stack Web App (Backend + Frontend)
```bash
python backend/server.py --port 8000
```
Open `http://127.0.0.1:8000` in your browser:
- Enter your **Personal No. K** at the top and click **Apply K**.
- Click **Run** and hold any key (or the **Hold Mouse / Spacebar to Press Key** button) to see your box appear and disappear on the 512×256 Hack screen.

### 3. Run Automated Tests
```bash
python -m unittest discover -s tests -v
```
# capastone-nand2tetris
