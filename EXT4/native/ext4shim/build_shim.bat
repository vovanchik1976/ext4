@echo off
setlocal

REM Set paths (adjust these according to your installation)
set E2=C:\dev\e2fs-mingw64
set GCC=gcc

REM Create bin directory if it doesn't exist
if not exist bin mkdir bin

REM Compile the shim
%GCC% -O2 -D_WIN32_WINNT=0x0601 ^
  -I"%E2%\include" -L"%E2%\lib" ^
  -shared -o bin/ext4shim.dll ext4shim.c ^
  -lext2fs -le2p -lcom_err -lz

echo Build completed.