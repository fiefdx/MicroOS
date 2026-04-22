import uos
import sys
import time
from math import ceil
from io import StringIO

from lib.shell import Shell
from lib.scheduler import Condition, Message
from lib.common import exists, path_join, isfile, isdir, path_split, Resource, abs_path, ram_size
from lib.display import Colors as C

coroutine = True


class PyShell(Shell):
    def __init__(self, display_size = (19, 9), cache_size = (-1, 50), history_length = 50, prompt_c = "\x00\x00\x00", scheduler = None, display_id = None, storage_id = None, history_file_path = "/.cache/.python_history"):
        self.display_width = display_size[0]
        self.display_height = display_size[1]
        self.display_width_with_prompt = display_size[0] + len(prompt_c)
        self.history_length = history_length
        self.prompt_c = prompt_c
        self.history = []
        self.cache_width = cache_size[0]
        self.cache_lines = cache_size[1]
        self.cache = []
        self.cursor_color = 1
        self.current_row = 0
        self.current_col = 0
        self.scheduler = scheduler
        self.display_id = display_id
        self.storage_id = storage_id
        self.cursor_row = 0
        self.cursor_col = 0
        self.history_idx = 0
        self.scroll_row = 0
        self.frame_history = []
        self.session_task_id = None
        self.exit = False
        self.current_shell = None
        self.enable_cursor = True
        self.history_file_path = history_file_path
        self.stats = ""
        self.loading = True
        self._line_chars = []  # list of chars for current input line (mutable, no alloc on append)
        self.load_history()
        self.clear()
        #Shell.__init__(self, display_size = display_size, cache_size = cache_size, history_length = history_length, prompt_c = prompt_c, scheduler = scheduler, display_id = display_id, storage_id = storage_id)
        #self.session_task_id = None
        #self.exit = False
        #self.current_shell = None
        
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
        if not hasattr(Resource, "python_history_file"):
            Resource.python_history_file = open(self.history_file_path, "a")
        self.history_file = Resource.python_history_file
        self.history_idx = len(self.history)
        
    def clear(self):
        self.term = StringIO()
        uos.dupterm(self.term)
        
    def exec_script(self, script, args = []):
        try:
            exec(script, {"args": args})
        except Exception as e:
            print(sys.print_exception(e))
        self.term.seek(0)
        lines = self.term.read().strip()
        lines = lines.replace("\r", "")
        self.clear()
        return lines
        
    def _line_str(self):
        """Convert current line chars to string. Only allocates when needed."""
        return "".join(self._line_chars)
    
    def input_char(self, c):
        if c == "\n":
            line_str = self._line_str()
            cmd = line_str.strip()
            if len(cmd) > 0:
                self.history.append(line_str)
                self.write_history(line_str)
                if cmd == "quit()":
                    self.exit = True
                    uos.dupterm(None)
                    self.cache.clear()
                    self.frame_history.clear()
                    self.history.clear()
                elif cmd == "clear()":
                    self.cache.clear()
                    self.frame_history.clear()
                    self.cache.append(self.prompt_c)
                    self.current_row = len(self.cache) - 1
                    self.current_col = len(self.prompt_c)
                    self._line_chars = []
                else:
                    if "=" in cmd or "for" in cmd or "import" in cmd or "from" in cmd or "if" in cmd:
                        try:
                            exec(cmd)
                        except Exception as e:
                            print(sys.print_exception(e))
                        self.term.seek(0)
                        lines = self.term.read().strip()
                        lines = lines.replace("\r", "")
                        self.write_lines(lines, end = True)
                        self.clear()
                    else:
                        try:
                            s = eval(cmd)
                            if s is not None:
                                self.write_lines(str(s).strip(), end = True)
                            else:
                                self.term.seek(0)
                                lines = self.term.read().strip()
                                lines = lines.replace("\r", "")
                                self.write_lines(lines, end = True)
                                self.clear()
                        except Exception as e:
                            print(sys.print_exception(e))
                            self.term.seek(0)
                            lines = self.term.read().strip()
                            lines = lines.replace("\r", "")
                            self.write_lines(lines, end = True)
                            self.clear()
            else:
                self.cache.append(self.prompt_c)
                self._line_chars = []
                self.cache_to_frame_history()
            if len(self.history) > self.history_length:
                self.history.pop(0)
            self.history_idx = len(self.history)
            self._line_chars = []
        elif c == "\b":
            if self.current_col > len(self.prompt_c):
                typed_pos = self.current_col - len(self.prompt_c) - 1
                del self._line_chars[typed_pos]
                self.cache[-1] = self.prompt_c + self._line_str()
                self.cursor_move_left()
        elif c == "BX":
            self.scroll_up()
        elif c == "BB":
            self.scroll_down()
        elif c == "UP":
            self.history_previous()
        elif c == "DN":
            self.history_next()
        elif c == "LT":
            self.cursor_move_left()
        elif c == "RT":
            self.cursor_move_right()
        elif c == "ES":
            pass
        elif len(c) == 1:
            typed_pos = self.current_col - len(self.prompt_c)
            self._line_chars.insert(typed_pos, c)
            self.cache[-1] = self.prompt_c + self._line_str()
            self.cursor_move_right()
                
        if len(self.cache) > self.cache_lines:
            self.cache.pop(0)
        self.current_row = len(self.cache)
        
    def write_char(self, c):
        if c == "\n":
            self.cache.append(self.prompt_c)
        else:
            self.cache[-1] += c
            if len(self.cache[-1]) > self.display_width_with_prompt:
                self.cache.append(" " + self.cache[-1][self.display_width_with_prompt:])
                self.cache[-2] = self.cache[-2][:display_width_with_prompt]
                
        if len(self.cache) > self.cache_lines:
            self.cache.pop(0)
        self.current_row = len(self.cache) - 1
        self.current_col = len(self.cache[-1])
        
    def write_lines(self, lines, end = False):
        lines = lines.split("\n")
        for n, line in enumerate(lines):
            line = line.replace("\r", "")
            line = line.replace("\n", "")
            if n == len(lines) - 1 and line == "":
                continue
            self.cache.append(line)
            if len(self.cache) > self.cache_lines:
                self.cache.pop(0)
            self.current_row = len(self.cache) - 1
            self.current_col = len(self.cache[-1])
        if end:
            self.write_char("\n")
        self.cache_to_frame_history()

    def update_stats(self, d):
        # self.stats = "[ C%3d%%|R%3d%%:%s|D %4dK|B[%s] %3d%%]" % (d[1], d[2], ram_size(d[3]), d[6] / 1024, "C" if d[8] else "D", d[9])
        self.stats = "[  CPU:%3d%%| RAM:%3d%%|%s|%s  ]" % (d[1], d[2], ram_size(d[3]), ram_size(d[4]))

    def get_display_frame(self, c = None):
        data = {}
        frame = self.cache_to_frame()[-self.display_height:]
        data["render"] = (("status", "texts"), )
        data["frame"] = frame
        data["cursor"] = self.get_cursor_position(c)
        data["status"] = [{"s": self.stats, "c": 40, "x": 0, "y": 310, "C": C.cyan}]
        if self.loading:
            # data["render"] = (("borders", "rects"),)
            # data["borders"] =[] # [[0, 0, 256, 127, 1], [0, 119, 256, 8, 1]]
            self.loading = False
        return data


def main(*args, **kwargs):
    task = args[0]
    name = args[1]
    shell = kwargs["shell"]
    shell_id = kwargs["shell_id"]
    shell.disable_output = True
    try:
        if len(kwargs["args"]) > 0:
            file_path = abs_path(kwargs["args"][0])
            result = []
            if exists(file_path):
                with open(file_path, "r") as fp:
                    content = fp.read()
                    s = PyShell(display_size = (37, 28))
                    result = s.exec_script(content, args = kwargs["args"][1:])
                shell.disable_output = False
                shell.current_shell = None
                yield Condition.get().load(sleep = 0, wait_msg = False, send_msgs = [
                    Message.get().load({"output": result}, receiver = shell_id)
                ])
            else:
                raise Exception("file[%s] not exists!" % file_path)
        else:
            s = PyShell(display_size = (37, 28))
            shell.current_shell = s
            s.write_line("            Welcome to Python")
            s.write_char("\n")
            yield Condition.get().load(sleep = 0, wait_msg = True, send_msgs = [
                Message.get().load(s.get_display_frame(), receiver = shell_id)
            ])
            msg = task.get_message()
            c = msg.content["msg"]
            msg.release()
            while not s.exit:
                #print("char:", c)
                s.input_char(c)
                if not s.exit:
                    yield Condition.get().load(sleep = 0, wait_msg = True, send_msgs = [
                        Message.get().load(s.get_display_frame(1 if c != "" else None), receiver = shell_id)
                    ])
                    msg = task.get_message()
                    c = msg.content["msg"]
                    msg.release()
            shell.disable_output = False
            shell.current_shell = None
            shell.loading = True
            s.cache = None
            s.history = None
            s.frame_history = None
            del s
            yield Condition.get().load(sleep = 0, wait_msg = False, send_msgs = [
                Message.get().load({"output": "quit from python"}, receiver = shell_id)
            ])
    except Exception as e:
        shell.disable_output = False
        shell.current_shell = None
        shell.loading = True
        yield Condition.get().load(sleep = 0, send_msgs = [
            Message.get().load({"output": str(e)}, receiver = shell_id)
        ])
