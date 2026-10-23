#!/bin/bash
# usage: liftc.sh <regex> <out>
python3 -I /home/claude/tools/lift.py /home/claude/cc/inno/app/UniwillService/MyControlCenter/GCUService.exe "$1" | python3 -c "
import re,sys
t=sys.stdin.read()
t=re.sub(r'\n  \w+: new String\[\d+\]\[\d+\] = [^\n]*','',t)
t=re.sub(r'\n  \w+: new CSharpArgumentInfo[^\n]*','',t)
t=re.sub(r'\n  \w+: if \(<>o__[^\n]*','',t)
t=re.sub(r'\n  \w+: <>o__\w+\.<>p__\d+ = TSpec\.Create[^\n]*','',t)
t=t.replace('this.GetType().get_Name(), ','')
sys.stdout.write(t)" > $2
wc -l $2
