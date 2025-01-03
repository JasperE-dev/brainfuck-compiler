from sys import argv as CLIargs
from subprocess import getstatusoutput 
from os import system
from enum import Enum as enum


class stack:
    def __init__(self):
        self.stack=[]
    def push(self,element:any):
        self.stack.append(element)
    def pop(self)->any:
        return self.stack.pop()
class Mode(enum):
    build=0
    run=1

def shell(cmd:str):
    exit_code,stdout=getstatusoutput(cmd)
    if exit_code!=0:
        print(stdout)
        quit(exit_code)

def getMatching(input:str,begin:str,end:str)->dict:
    # remove all chars that arn't begin or end
    out=[]
    found=False
    for index,char in enumerate(input):
        if char==begin or char==end:
            found=True
            out.append((char,index))
    if not found:
        return {}
    # determine matching
    input=out
    matching={}
    nested=stack()
    error=False
    for index,_ in enumerate(input):
        char,location=_
        if   char=='[':
            nested.push(location)
        elif char==']':
            try: 
                matching[nested.pop()]=location
            except IndexError: # assume it was triggered  by 'pop from empty list' 
                print(f'ERROR: missing "[" matching to "]" at {index}')
                error=True

    if len(nested.stack)!=0:
        error=True
        for missing in nested.stack:
            print(f'ERROR: missing "]" matching to "[" at {missing}')
    if error:
        quit(1)
    return matching
        

helpMsg="""usage  python [option(s)] [cmd] file
build  compile file and create elf64 executable
run    compile file and create elf64 executable, that is then execute and deleted
"""

# todo:
#  optimize
#  +++ -> +3, >+< -> +1 next cell
#
#  settings ,extensions, examples whit readme.md

default=Mode.run

if len(CLIargs)==1 or len(CLIargs)>=4:
    print(helpMsg,end='')
    quit(0)
elif len(CLIargs)==2:
    mode=default
    file=CLIargs[1]
elif len(CLIargs)==3:
    file=CLIargs[2]

    match CLIargs[1]:
        case 'build':
            mode=Mode.build
        case 'run':
            mode=Mode.run
        case _:
            print(f'ERROR: unknown command "{CLIargs[1]}"')
            quit(1)

input=open(file,'r').read()

matching=getMatching(input,'[',']')

matchingRevers={}
for key,value in matching.items():
    matchingRevers[value]=key

tapeSize=3000
code=''
label=0

for index,char in enumerate(input):
    match char:
        case '>': # move tapeHead right/forward 
            label+=1
            code+='inc r15\n'
            code+=f'cmp r15,{tapeSize}\n'
            code+=f'jne skip{label}; check for overflow\n'
            code+='mov r15,0\n'
            code+=f'skip{label}:\n'
            code+='\n'
        case '<': # move tapeHead left/backwards
            label+=1
            code+='cmp r15,0\n'
            code+=f'jne skip{label}; check for overflow\n'
            code+=f'mov r15,{tapeSize-1}\n'
            code+=f'jmp end{label}\n'
            code+=f'skip{label}:\n'
            code+='dec r15\n'
            code+=f'end{label}:\n'
            code+='\n'
        case '+': # increment current cell under tapeHead by one
            code+='inc byte [r15+tape]\n'
            code+='\n'
        case '-': # decrement current cell under tapeHead by one
            code+='dec byte [r15+tape]\n'
            code+='\n'
        case '[': # jump past the matching ] if current cell under tapeHead is 0
            code+='cmp byte [tape+r15],0\n'
            code+=f'je jump{matching[index]}\n'
            code+=f'loop{index}:\n'
            code+='\n'
        case ']': # jump back to the matching [ if current cell under tapeHead is higher than 0
            code+='cmp byte [tape+r15],0\n'
            code+=f'jne loop{matchingRevers[index]}\n'
            code+=f'jump{index}:\n'
            code+='\n'
        case '.': # print ASCII value of current cell under tapeHead
            code+='mov rax, 1\n'
            code+='mov rdi, 1\n'
            code+='mov rsi, r15\n'
            code+='add rsi, tape\n'
            code+='mov rdx, 1\n'
            code+='syscall\n'
            code+='\n'
        case ',': # set value of current cell under tapeHead to number code of one key press 
            code+='mov rax, 0\n'
            code+='mov rdi, 1\n'
            code+='mov rsi, r15\n'
            code+='add rsi, tape\n'
            code+='mov rdx, 1\n'
            code+='syscall\n'
            code+='\n'
        case _:
            pass

name=file.split('/')[-1]
name=name.split('.')[0]
open(f'{name}.asm','w').write(f'''BITS 64 ; 32 would be faster but oh well

global _start

section .data

section .bss
tape: resb {tapeSize}

termios:
  c_iflag resd 1   ; input mode flags
  c_oflag resd 1   ; output mode flags
  c_cflag resd 1   ; control mode flags
  c_lflag resd 1   ; local mode flags
  c_line  resb 1   ; line discipline
  c_cc    resb 19  ; control characters

section .text

_start:

mov  eax, 16      ; ioctl
mov  edi, 0       ; fd stdin
mov  esi, 0x5401  ; TCGETS
mov  rdx, termios ; prt to struct
syscall

and byte [c_lflag], 0x0fd  ; Clear ICANON to disable canonical/cooked mode and set it to raw mode

mov  eax, 16      ; ioctl
mov  edi, 0       ; fd stdin
mov  esi, 0x5402  ; TCSETS
mov  rdx, termios ; prt to struct
syscall


; r15 is tapeHead
{code}

; if you ctr+v then you can stile enter more then one char in to stdin buf even tho terminal is in raw mode, but oh well thats what flush is for
mov rax, 16    ; ioctl
mov rdi, 1     ; fd stdin
mov rsi, 21515 ; TCFLSH/flush
mov rdx, 0     ; TCIFLUSH/flush receive not transmit 
syscall


mov rax,60 ; exit
mov rdi,0  ; exit code 0
syscall
''')

shell(f'nasm -felf64 -o {name}.o {name}.asm')
shell(f'ld -o {name} {name}.o')
shell(f'rm {name}.asm {name}.o')

if mode==Mode.run:
    system(f'./{name}')
    shell(f'rm {name}')


