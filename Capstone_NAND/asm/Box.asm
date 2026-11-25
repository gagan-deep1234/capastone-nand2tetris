// Part C - Box.asm
// Nand to Tetris I (ETCCNT301) Capstone Project
// Draws a black box while any key is pressed; clears it when released.
//
// Generated for Personal Number K = 41:
//   Start row   = K = 41
//   Height      = 20 rows (rows 41..60)
//   Width       = 16 * ((K mod 4) + 1) = 16 * 2 = 32 pixels (2 words per row)
//   Start addr  = SCREEN + 32 * 41 = 16384 + 1312 = 17696

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
    @17696          // Start address = SCREEN (16384) + 32 * 41
    D=A
    @rowPtr
    M=D

    @20             // Box height = 20 rows
    D=A
    @rowCount
    M=D

(ROW_LOOP)
    @rowCount
    D=M
    @LOOP
    D;JEQ           // Finished all 20 rows -> poll keyboard again

    @rowPtr
    D=M
    @addr
    M=D             // addr = start of current row

    @2              // Width in words = (41 mod 4) + 1 = 2 words (32 pixels)
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
    @32
    D=A
    @rowPtr
    M=D+M           // Advance to next screen row (+32 words)

    @rowCount
    M=M-1
    @ROW_LOOP
    0;JMP
