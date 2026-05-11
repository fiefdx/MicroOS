#!/bin/bash
cmd_path=$(dirname $0)
cd $cmd_path

# ls | egrep '.py' | awk '{print "mpy-cross ./"$1}'
rm ./*.mpy
rm -rf ./build
mkdir ./build
mkdir ./build/bin
mkdir ./build/lib
mkdir ./build/lib/mrequests

cd ./lib
rm -f ./*.mpy
mpy-cross ./analyzer.py
mpy-cross ./basic_shell_alone.py
mpy-cross ./basicparser.py
mpy-cross ./basictoken.py
mpy-cross ./chunk.py
mpy-cross ./common.py
mpy-cross ./dictfile.py
mpy-cross ./dictfile2.py
mpy-cross ./display.py
mpy-cross ./flowsignal.py
mpy-cross ./font.py
mpy-cross ./font6.py
mpy-cross ./font7.py
mpy-cross ./font8.py
mpy-cross ./interpreter.py
mpy-cross ./keyboard.py
mpy-cross ./lexer.py
mpy-cross ./listfile_safe.py
mpy-cross ./listfile.py
mpy-cross ./ntp.py
mpy-cross ./ollama.py
mpy-cross ./program.py
mpy-cross ./reload.py
mpy-cross ./request.py
mpy-cross ./scheduler.py
mpy-cross ./sdcard.py
mpy-cross ./shell.py
mpy-cross ./tea.py
mpy-cross ./uftpd.py
mpy-cross ./uping.py
mpy-cross ./urtc.py
mpy-cross ./utarfile.py
mpy-cross ./wave.py
mpy-cross ./wifi.py
# mpy-cross ./writer_fast.py
mpy-cross ./writer.py
mpy-cross ./zipfile.py
mpy-cross ./zlib.py
mpy-cross ./mrequests/mrequests.py
mpy-cross ./mrequests/urlencode.py
mpy-cross ./mrequests/urlparseqs.py
mpy-cross ./mrequests/urlunquote.py

cp -f ./__init__.py ../build/lib/
mv -f ./*.mpy ../build/lib/
cp -f ./mrequests/__init__.py ../build/lib/mrequests/
mv -f ./mrequests/*.mpy ../build/lib/mrequests/

cd ../bin
rm -f ./*.mpy
ls | egrep '.py' | grep -v '__init__.py' | awk '{print "mpy-cross ./"$1}' | bash
cp -f ./__init__.py ../build/bin/
mv -f ./*.mpy ../build/bin/