import os
import sys
import uos
import gc
import time
import machine
from math import ceil
from io import StringIO
from machine import Pin, I2C
from micropython import const

from .basictoken import BASICToken as Token
from .lexer import Lexer
from .program import Program

from .listfile import ListFile
from .scheduler import Scheduler, Condition, Task, Message
from .common import exists, path_join, isfile, isdir, path_split, mkdirs, copy, get_size, copyfile, copydir, rmtree


class BasicShell(object):
    def __init__(self, display_size = (19, 9), cache_size = (-1, 50), history_length = 50, prompt_c = ">", scheduler = None, display_id = None, storage_id = None, history_file_path = "/.cache/.history_basic", bin_path = "/bin", ram_path = "/.cache/.ram"):
        self.display_width = const(display_size[0])
        self.display_height = const(display_size[1])
        self.display_width_with_prompt = const(display_size[0] + len(prompt_c))
        self.history_length = const(history_length)
        self.prompt_c = const(prompt_c)
        self.history = []
        self.cache_width = const(cache_size[0])
        self.cache_lines = const(cache_size[1])
        self.cache = []
        self.cursor_color = 1
        self.current_row = 0
        self.current_col = 0
        self.scheduler = scheduler
        self.display_id = const(display_id)
        self.storage_id = const(storage_id)
        self.cursor_row = 0
        self.cursor_col = 0
        self.history_idx = 0
        self.scroll_row = 0
        self.frame_history = []
        self.session_task_id = None
        self.disable_output = False
        self.current_shell = None
        self.enable_cursor = True
        self.history_file_path = const(history_file_path)
        self.bin_path = const(bin_path)
        self.load_history()
        self.lexer = Lexer()
        self.ram_path = ram_path
        self.ram = False
        if exists(self.ram_path):
            self.ram = True
            self.prompt_c = "#"
        Program.print = self.print
        self.program = Program(ram = self.ram)
        self.run_program_id = None
        self.wait_for_input = False
        self.input_start = None
        self.input_counter = 0

    def load_history(self):
        if exists(self.history_file_path):
            history_file = open(self.history_file_path, "r")
            history_lines = 0
            line = history_file.readline()
            while line:
                line = line.strip()
                self.history.append(line)
                if len(self.history) > self.history_length:
                    self.history.pop(0)
                history_lines += 1
                line = history_file.readline()
            history_file.close()
            if history_lines > self.history_length:
                tmp_file_path = self.history_file_path + ".tmp"
                if exists(tmp_file_path):
                    uos.remove(tmp_file_path)
                uos.rename(self.history_file_path, tmp_file_path)
                tmp_file = open(tmp_file_path, "r")
                history_file = open(self.history_file_path, "w")
                l = 0
                line = tmp_file.readline()
                while line:
                    l += 1
                    if l > (history_lines - self.history_length):
                        history_file.write(line)
                    line = tmp_file.readline()
                tmp_file.close()
                history_file.close()
                uos.remove(tmp_file_path)
        self.history_file = open(self.history_file_path, "a")
        self.history_idx = len(self.history)
        
    def write_history(self, line):
        if line[-1] != "\n":
            line += "\n"
        self.history_file.write(line)
        self.history_file.flush()
    
    def get_display_frame(self):
        # return self.cache[-self.display_height:]
        data = {}
        frame = self.cache_to_frame()[-self.display_height:]
        data["frame"] = frame
        data["cursor"] = self.get_cursor_position(1)
        return data
    
    def cache_to_frame_history(self):
        self.frame_history.clear()
        for n, line in enumerate(self.cache[:-1]):
            for i in range(ceil(len(line) / self.display_width_with_prompt)):
                self.frame_history.append(line[i*self.display_width_with_prompt:(i+1)*self.display_width_with_prompt])
                
    def history_to_frame(self, last_lines, scroll_row):
        frame = []
        total_lines = len(self.frame_history) + len(last_lines)
        end_idx = total_lines + scroll_row - 1
        start_idx = total_lines + scroll_row - self.display_height
        if start_idx < 0:
            start_idx = 0
            end_idx = start_idx + self.display_height - 1
            self.scroll_row = self.display_height - total_lines
        if end_idx >= total_lines:
            end_idx = total_lines - 1
        if start_idx >= 0 and start_idx < len(self.frame_history):
            if end_idx >= 0 and end_idx < len(self.frame_history):
                for i in range(start_idx, end_idx + 1):
                    frame.append(self.frame_history[i])
            else:
                for i in range(start_idx, len(self.frame_history)):
                    frame.append(self.frame_history[i])
                for i in range(0, end_idx - len(self.frame_history) + 1):
                    frame.append(last_lines[i])
        else:
            for i in range(start_idx - len(self.frame_history), end_idx - len(self.frame_history) + 1):
                frame.append(last_lines[i])
        return frame
    
    def cache_to_frame(self):
        frame = []
        self.cursor_row = 0
        self.cursor_col = 0
        row = -1
        if self.scroll_row == 0:
            lines = self.cache[-self.display_height:]
            for n, line in enumerate(lines):
                if len(line) > 0:
                    for i in range(ceil(len(line) / self.display_width_with_prompt)):
                        frame.append(line[i*self.display_width_with_prompt:(i+1)*self.display_width_with_prompt])
                        row += 1
                        if len(frame) > self.display_height:
                            frame.pop(0)
                            row -= 1
                        if n == len(lines) - 1: # last line in cache
                            if ceil(self.current_col / self.display_width_with_prompt) == (i + 1): # cursor in current line
                                self.cursor_row = row
                                self.cursor_col = self.current_col % self.display_width_with_prompt
                                if self.cursor_col == 0:
                                    self.cursor_col = 42
                                #print("cursor_row: ", row, "cursor_col: ", self.cursor_col)
                            elif ceil(self.current_col / self.display_width_with_prompt) < (i + 1):
                                if len(frame) >= self.display_height:
                                    self.cursor_row -= 1
                else:
                    frame.append(line)
                    row += 1
                    self.cursor_row = row
        else:
            frame_lines = []
            line = self.cache[-1]
            for i in range(ceil(len(line) / self.display_width_with_prompt)):
                frame_lines.append(line[i*self.display_width_with_prompt:(i+1)*self.display_width_with_prompt])
            frame = self.history_to_frame(frame_lines, self.scroll_row)
        if self.cursor_row >= self.display_height:
            self.cursor_row = self.display_height - 1
        return frame
        
    def get_cursor_position(self, c = None):
        #print("get_cursor_position:", self.cursor_col, self.cursor_row)
        if self.current_shell:
            return self.current_shell.get_cursor_position(c)
        if self.enable_cursor:
            return self.cursor_col, self.cursor_row, self.cursor_color if c is None else c
        else:
            return self.cursor_col, self.cursor_row, 0
    
    def set_cursor_position(self, col, row):
        #print("set_cursor_position:", col, row)
        self.cursor_col, self.cursor_row = col, row
    
    def set_cursor_color(self, c):
        if self.current_shell:
            self.current_shell.set_cursor_color(c)
        self.cursor_color = c
    
    def get_cursor_cache_position(self, c = None):
        return self.current_col, self.current_row if self.current_row <= (self.display_height - 1) else (self.display_height - 1), self.cursor_color if c is None else c
    
    def input_char(self, c):
        try:
            if c == "\n":
                cmd = self.cache[-1].strip()
                if cmd.startswith(self.prompt_c):
                    cmd = cmd[len(self.prompt_c):]
                if len(cmd) > 0:
                    if cmd.lower() == "exit":
                        self.history.append(self.cache[-1][len(self.prompt_c):])
                        self.write_history(self.cache[-1][len(self.prompt_c):])
                        if exists("/main.basic.py"):
                            uos.rename("/main.py", "/main.shell.py")
                            uos.rename("/main.basic.py", "/main.py")
                            machine.soft_reset()
                        elif exists("/main.shell.py"):
                            uos.rename("/main.py", "/main.basic.py")
                            uos.rename("/main.shell.py", "/main.py")
                            machine.soft_reset()
                    elif cmd.startswith("ls"):
                        self.history.append(self.cache[-1][len(self.prompt_c):])
                        self.write_history(self.cache[-1][len(self.prompt_c):])
                        ps = cmd.replace("ls", "").strip().split(" ")
                        args = ps
                        self.print(self.ls(args))
                    elif cmd.startswith("cd"):
                        self.history.append(self.cache[-1][len(self.prompt_c):])
                        self.write_history(self.cache[-1][len(self.prompt_c):])
                        p = cmd.replace("cd", "").strip()
                        args = [p] if len(p) > 0 else []
                        self.print(self.cd(args))
                    elif cmd.startswith("pwd"):
                        self.history.append(self.cache[-1][len(self.prompt_c):])
                        self.write_history(self.cache[-1][len(self.prompt_c):])
                        self.print(self.pwd())
                    elif cmd.startswith("rm"):
                        self.history.append(self.cache[-1][len(self.prompt_c):])
                        self.write_history(self.cache[-1][len(self.prompt_c):])
                        p = cmd.replace("rm", "").strip()
                        args = [p] if len(p) > 0 else []
                        self.print(self.rm(args))
                    elif cmd.startswith("mkdir"):
                        self.history.append(self.cache[-1][len(self.prompt_c):])
                        self.write_history(self.cache[-1][len(self.prompt_c):])
                        p = cmd.replace("mkdir", "").strip()
                        args = [p] if len(p) > 0 else []
                        self.print(self.mkdir(args))
                    elif cmd.startswith("free"):
                        self.history.append(self.cache[-1][len(self.prompt_c):])
                        self.write_history(self.cache[-1][len(self.prompt_c):])
                        self.print(self.free())
                    elif cmd.startswith("ram"):
                        self.history.append(self.cache[-1][len(self.prompt_c):])
                        self.write_history(self.cache[-1][len(self.prompt_c):])
                        self.print(self.ram_switch())
                    elif cmd.startswith("reboot"):
                        self.history.append(self.cache[-1][len(self.prompt_c):])
                        self.write_history(self.cache[-1][len(self.prompt_c):])
                        self.print(self.reboot())
                    elif cmd.startswith("shutdown"):
                        self.history.append(self.cache[-1][len(self.prompt_c):])
                        self.write_history(self.cache[-1][len(self.prompt_c):])
                        self.print(self.shutdown())
                    elif self.run_program_id != None:
                        self.send_input_hook(self.cache[-1])
                        self.print("")
                    else:
                        self.history.append(self.cache[-1][len(self.prompt_c):])
                        self.write_history(self.cache[-1][len(self.prompt_c):])
                        try:
                            lines = ""
                            tokenlist = self.lexer.tokenize(cmd)

                            # Execute commands directly, otherwise
                            # add program statements to the stored
                            # BASIC program

                            if len(tokenlist) > 0:

                                # Add a new program statement, beginning
                                # a line number
                                if tokenlist[0].category == Token.UNSIGNEDINT\
                                     and len(tokenlist) > 1:
                                    self.program.add_stmt(tokenlist)
                                    self.print("")

                                # Delete a statement from the program
                                elif tokenlist[0].category == Token.UNSIGNEDINT \
                                        and len(tokenlist) == 1:
                                    self.program.delete_statement(int(tokenlist[0].lexeme))
                                    self.print("")

                               # Execute the program
                                elif tokenlist[0].category == Token.RUN:
                                    self.run_program_id = self.scheduler.add_task(
                                        Task.get().load(self.program.execute,
                                              "basic-execute",
                                              kwargs = {"execute_print": self.execute_print, "shell": self}
                                         )
                                    )
                                    self.print("")

                                # List the program
                                elif tokenlist[0].category == Token.LIST:
                                     if len(tokenlist) == 2:
                                         self.program.list(int(tokenlist[1].lexeme),int(tokenlist[1].lexeme))
                                     elif len(tokenlist) == 3:
                                         # if we have 3 tokens, it might be LIST x y for a range
                                         # or LIST -y or list x- for a start to y, or x to end
                                         if tokenlist[1].lexeme == "-":
                                             self.program.list(None, int(tokenlist[2].lexeme))
                                         elif tokenlist[2].lexeme == "-":
                                             self.program.list(int(tokenlist[1].lexeme), None)
                                         else:
                                             self.program.list(int(tokenlist[1].lexeme),int(tokenlist[2].lexeme))
                                     elif len(tokenlist) == 4:
                                         # if we have 4, assume LIST x-y or some other
                                         # delimiter for a range
                                         self.program.list(int(tokenlist[1].lexeme),int(tokenlist[3].lexeme))
                                     else:
                                         self.program.list()
                                     self.print("")

                                # Save the program to disk
                                elif tokenlist[0].category == Token.SAVE:
                                    self.program.save(tokenlist[1].lexeme)
                                    lines += "Program written to file\n"

                                # Load the program from disk
                                elif tokenlist[0].category == Token.LOAD:
                                    self.program.load(tokenlist[1].lexeme)
                                    lines += "Program read from file\n"

                                # Delete the program from memory
                                elif tokenlist[0].category == Token.NEW:
                                    self.program.delete()
                                    self.print("")                                

                                # Unrecognised input
                                else:
                                    self.print("Unrecognised input", end = "")
                                    for token in tokenlist:
                                        token.print_lexeme()
                                    self.print("")
                                if len(lines) > 0:
                                    self.print(lines)
                        except Exception as e:
                            self.print(e)
                else:
                    self.cache.append(self.prompt_c)
                    self.cache_to_frame_history()
                if len(self.history) > self.history_length:
                    self.history.pop(0)
                self.history_idx = len(self.history)
                self.input_counter += 1
            elif c == "\b":
                if len(self.cache[-1][:self.current_col]) > len(self.prompt_c):
                    self.cache[-1] = self.cache[-1][:self.current_col-1] + self.cache[-1][self.current_col:]
                    self.cursor_move_left()
                    self.input_counter += 1
            elif c == "BX":
                self.scroll_up()
                self.input_counter += 1
            elif c == "BB":
                self.scroll_down()
                self.input_counter += 1
            elif c == "UP":
                self.history_previous()
                self.input_counter += 1
            elif c == "DN":
                self.history_next()
                self.input_counter += 1
            elif c == "LT":
                self.cursor_move_left()
                self.input_counter += 1
            elif c == "RT":
                self.cursor_move_right()
                self.input_counter += 1
            elif c == "ES":
                pass
            elif c == "Ctrl-C":
                self.kill_program()
            elif len(c) == 1:
                if self.wait_for_input and self.input_start is None:
                    self.input_start = len(self.cache[-1])
                self.cache[-1] = self.cache[-1][:self.current_col] + c + self.cache[-1][self.current_col:]
                self.cursor_move_right()
                    
            if len(self.cache) > self.cache_lines:
                self.cache.pop(0)
            self.current_row = len(self.cache)
        except Exception as e:
            self.print(str(e))
            self.print("")

    def free(self):
        gc.collect()
        ram_free = gc.mem_free()
        ram_used = gc.mem_alloc()
        message = "R%6.2f%%|F%7.2fk/%d|U%7.2fk/%d\n" % (100.0 - (ram_free * 100 / (264 * 1024)),
                                                        ram_free / 1024,
                                                        ram_free,
                                                        ram_used / 1024,
                                                        ram_used)
        message += "Message[%s/%s] Condition[%s/%s] Task[%s/%s]" % (
            Message.remain(), len(Message.pool),
            Task.remain(), len(Task.pool),
            Task.remain(), len(Task.pool)
        )
        return message

    def ram_switch(self):
        if exists(self.ram_path):
            uos.remove(self.ram_path)
            return "disk mode after reboot"
        else:
            with open(self.ram_path, "w") as fp:
                pass
            return "ram mode after reboot"

    def ls(self, args = []):
        files = []
        files_total = 0
        dirs_total = 0
        path = uos.getcwd()
        page_size = 16
        page_num = 1
        if len(args) > 0:
            path = args[0]
        if len(args) > 1:
            page_num = int(args[1])
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]
        fs = uos.ilistdir(path)
        for f in fs:
            if f[1] == 16384:
                dirs_total += 1
            elif f[1] == 32768:
                files_total += 1
        start = (page_num - 1) * page_size
        end = page_num * page_size
        stop = False
        n = 0
        fs = uos.ilistdir(path)
        for f in fs:
            if f[1] == 16384:
                n += 1
                if n >= start and n <= end:
                    files.append("D:" + f[0])
                if n >= end:
                    stop = True
                    break
        if not stop:
            fs = uos.ilistdir(path)
            for f in fs:
                if f[1] == 32768:
                    n += 1
                    if n >= start and n <= end:
                        files.append("F:" + f[0])
                    if n >= end:
                        break
        files.append("Total-%s|Dirs-%s|Files-%s|%s-%s:%s/%s" % (
            dirs_total + files_total,
            dirs_total,
            files_total,
            start + 1,
            end,
            page_num,
            ceil((dirs_total + files_total) / page_size))
        )
        result = "\n".join(files)
        return result

    def pwd(self):
        return uos.getcwd()

    def cd(self, args = []):
        result = "path invalid"
        path = "/sd"
        if len(args) > 0:
            path = args[0]
        if exists(path) and uos.stat(path)[0] == 16384:
            uos.chdir(path)
            result = path
        return result

    def rm(self, args = []):
        result = "invalid parameters"
        if len(args) == 1:
            t_path = args[0]
            cwd = uos.getcwd()
            if t_path.startswith("."):
                t_path = cwd + t_path[1:]
            n = 1
            result = ""
            for output in rmtree(t_path):
                n += 1
                result += output + "\n"
            result = result[:-1]
        return result

    def mkdir(self, args = []):
        result = "already exists!"
        cwd = uos.getcwd()
        if len(args) > 0:
            path = args[0]
            if path.startswith("."):
                path = cwd + path[1:]
            if path.endswith("/"):
                path = path[:-1]
            if not exists(path):
                mkdirs(path)
                result = path
        return result

    def reboot(self):
        machine.soft_reset()

    def shutdown(self):
        pass

    def kill_task(self, task, name):
        yield task.condition.load(sleep = 0, send_msgs = [Message.get().load({"msg": "Ctrl-C"}, receiver = self.run_program_id)])
        self.run_program_id = None
        
    def kill_program(self):
        if self.run_program_id != None:
            #self.run_program_id = None
            self.scheduler.add_task(Task.get().load(self.kill_task, "kill", kwargs = {}))
            
    def send_input(self, task, name, msg = ""):
        yield task.condition.load(sleep = 0, send_msgs = [Message.get().load({"msg": msg}, receiver = self.run_program_id)])
    
    def send_input_hook(self, line):
        self.scheduler.add_task(Task.get().load(self.send_input, "send_input", kwargs = {"msg": line[self.input_start:]}))
        self.wait_for_input = False
        self.input_start = None
        
    def write_char(self, c, terminated = False):
        if c == "\n":
            if self.run_program_id is None or terminated:
                self.cache.append(self.prompt_c)
            else:
                self.cache.append("")
        else:
            self.cache[-1] += c
            if len(self.cache[-1]) > self.display_width_with_prompt:
                self.cache.append(" " + self.cache[-1][self.display_width_with_prompt:])
                self.cache[-2] = self.cache[-2][:display_width_with_prompt]
                
        if len(self.cache) > self.cache_lines:
            self.cache.pop(0)
        self.current_row = len(self.cache) - 1
        self.current_col = len(self.cache[-1])
        self.input_counter += 1
        
    def print(self, *objects, sep = ' ', end = '\n', file = None, flush = True):
        lines = ""
        for i, o in enumerate(objects):
            lines += str(o).replace("\r", "")
            if i < len(objects) - 1:
                lines += sep # '\n' if sep == '' else sep
        self.write_lines(lines, end = True if end == '\n' else False)
        self.input_counter += 1
        
    def write_lines(self, lines, end = True):
        lines = lines.split("\n")
        for line in lines:
            if len(line) > 0:
                line = line.replace("\r", "")
                line = line.replace("\n", "")
                self.cache.append(line)
                if len(self.cache) > self.cache_lines:
                    self.cache.pop(0)
                self.current_row = len(self.cache) - 1
                self.current_col = len(self.cache[-1])
        if end:
            self.write_char("\n")
        self.cache_to_frame_history()
        
    def execute_print(self, *objects, sep = ' ', end = '', file = None, flush = True, terminated = False):
        lines = ""
        for i, o in enumerate(objects):
            lines += str(o).replace("\r", "").replace("\t", " ")
            if i < len(objects) - 1:
                lines += sep # '\n' if sep == '' else sep
        self.execute_write_lines(lines, end = True if end == '\n' else False, terminated = terminated)
        self.input_counter += 1
        
    def execute_write_lines(self, lines, end = True, terminated = False):
        #lines = lines.split("\n")
        lines = [lines]
        for line in lines:
            if len(line) > 0:
                line = line.replace("\r", "")
                line = line.replace("\n", "")
                if self.wait_for_input:
                    self.cache[-1] += line
                else:
                    #if line.endswith("\n"):
                    #    self.cache[-1] += line
                    #    self.cache.append("")
                    #else:
                    self.cache[-1] += line
                    #self.cache.append(line)
                if len(self.cache) > self.cache_lines:
                    self.cache.pop(0)
                self.current_row = len(self.cache) - 1
                self.current_col = len(self.cache[-1])
        if end:
            self.write_char("\n", terminated = terminated)
        self.cache_to_frame_history()

    def diff_frame(self, f1, f2):
        if f1 is None or f2 is None:
            return True
        elif len(f1) != len(f2):
            return True
        for i in range(len(f1)):
            if f1[i] != f2[i]:
                return True
        return False
            
    def write_line(self, line):
        self.cache.append(line)
        if len(self.cache) > self.cache_lines:
            self.cache.pop(0)
        self.current_row = len(self.cache) - 1
        self.current_col = len(self.cache[-1])
        self.cache_to_frame_history()
            
    def write(self, s):
        line_width = self.display_width_with_prompt
        d = s[:line_width]
        s = s[line_width:]
        while len(d) > 0:
            self.cache.append(d)
            if len(self.cache) > self.cache_lines:
                self.cache.pop(0)
            self.current_row = len(self.cache) - 1
            self.current_col = len(self.cache[-1])
            d = s[:line_width]
            s = s[line_width:]
        self.write_char("\n")
        self.cache_to_frame_history()
            
    def run(self, task, cmd):
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"cmd": cmd}, receiver = self.storage_id)
        ])
        
    def send_session_message(self, task, msg):
        #print("send_session_message:", msg, self.session_task_id)
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"msg": msg}, receiver = self.session_task_id)
        ])
        
    def run_coroutine(self, task, cmd):
        #print("run_coroutine: ", task, cmd)
        #import bin
        args = cmd.split(" ")
        module = args[0].split(".")[0]
        #if "/sd/usr" not in sys.path:
        #    sys.path.insert(0, "/sd/usr")
        #import bin
        if module not in sys.modules:
            #import_str = "from bin import %s" % module
            import_str = "import %s; sys.modules['%s'] = %s" % (module, module, module)
            exec(import_str)
        #bin.__dict__[]
        #self.session_task_id = self.scheduler.add_task(Task(bin.__dict__[module].main, cmd, kwargs = {"args": args[1:], "shell_id": self.scheduler.shell_id, "shell": self}, need_to_clean = [bin.__dict__[module]])) # execute cmd
        self.session_task_id = self.scheduler.add_task(
            Task.get().load(sys.modules[module].main, cmd, kwargs = {"args": args[1:],
                                                                                       "shell_id": self.scheduler.shell_id,
                                                                                       "shell": self}, need_to_clean = [sys.modules[module]])
        ) # execute cmd
    
    def cursor_move_left(self):
        if self.current_col > len(self.prompt_c):
            self.current_col -= 1
        #print("current_col: ", self.current_col)
    
    def cursor_move_right(self):
        if self.current_col < len(self.cache[-1]):
            self.current_col += 1
        #print("current_col: ", self.current_col)
        
    def scroll_up(self):
        self.scroll_row -= 18
        #print("scroll_row:", self.scroll_row)
        
    def scroll_down(self):
        self.scroll_row += 18
        if self.scroll_row >= 0:
            self.scroll_row = 0
        #print("scroll_row:", self.scroll_row)
    
    def history_previous(self):
        self.history_idx -= 1
        if self.history_idx <= 0:
            self.history_idx = 0
        #print("history:", self.history, self.history_idx)
        if len(self.history) > 0:
            #if self.history_idx > len(self.history) - 1:
            #    self.history_idx = len(self.history) - 1
            #print("history:", self.history, self.history_idx)
            self.cache[-1] = self.prompt_c + self.history[self.history_idx]
            self.current_row = len(self.cache) - 1
            self.current_col = len(self.cache[-1])
        
    def history_next(self):
        self.history_idx += 1
        if self.history_idx > len(self.history) - 1:
            self.history_idx = len(self.history)
        #print("history:", self.history, self.history_idx)
        if len(self.history) > 0:
            if self.history_idx > len(self.history) - 1:
                self.cache[-1] = self.prompt_c
            else:
                self.cache[-1] = self.prompt_c + self.history[self.history_idx]
            #print("history:", self.history, self.history_idx)
            self.current_row = len(self.cache) - 1
            self.current_col = len(self.cache[-1])
