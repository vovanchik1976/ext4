@echo off
setlocal

REM Set paths (adjust these according to your installation)
set E2FSPREFIX=C:\dev\e2fs-mingw64
set GCC=gcc

REM Create bin directory if it doesn't exist
if not exist bin mkdir bin

REM Compile the shim with proper flags
%GCC% -O2 -D_WIN32_WINNT=0x0601 ^
  -I"%E2FSPREFIX%\include" -L"%E2FSPREFIX%\lib" ^
  -shared -o bin/ext4shim.dll ext4shim.c ^
  -lext2fs -le2p -lcom_err -lz

echo Build completed.