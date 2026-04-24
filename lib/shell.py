import sys
import uos
from io import StringIO
from micropython import const

# from listfile import ListFile
from .scheduler import Condition, Task, Message
from .common import exists, path_join, isfile, isdir, path_split, abs_path, Resource, ClipBoard, ram_size
from .display import Colors as C


class Shell(object):
    def __init__(self, display_size = (20, 8), cache_size = (-1, 50), history_length = 100, prompt_c = "\x00", scheduler = None, display_id = None, storage_id = None, history_file_path = "/.cache/.history", bin_path = "/bin", shell_id = 0):
        self.display_width = const(display_size[0])
        self.display_height = const(display_size[1])
        self.display_width_with_prompt = const(display_size[0] + len(prompt_c))
        self.history_length = const(history_length)
        self.prompt_c = const(prompt_c)
        self.history = [] # ListFile("./shell_history_cache.json", shrink_threshold = 10240) # 86.86k free for [], 88.05k for ListFile
        self.cache_width = const(cache_size[0])
        self.cache_lines = const(cache_size[1])
        self.cache = [] # ListFile("./shell_cache.json", shrink_threshold = 10240)
        self.cursor_color = 1
        self.current_row = 0
        self.current_col = 0
        self.scheduler = scheduler
        self.display_id = const(display_id)
        self.storage_id = const(storage_id)
        self.cursor_row = 0
        self.cursor_col = 0
        self.cursor_id = None
        self.history_idx = 0
        self.scroll_row = 0
        self.frame_history = [] # ListFile("./shell_frame_history_cache.json", shrink_threshold = 10240) # 90.81k for ListFile
        self.session_task_id = None
        self.disable_output = False
        self.current_shell = None
        self.enable_cursor = True
        self.history_file_path = const(history_file_path)
        self.bin_path = const(bin_path)
        self.stats = ""
        self.loading = True
        self.shell_id = shell_id
        self._line_chars = []  # list of chars for current input line (mutable, no alloc on append)
        self.load_history()
    
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
        if not hasattr(Resource, "history_file"):
            Resource.history_file = open(self.history_file_path, "a")
        self.history_file = Resource.history_file
        self.history_idx = len(self.history)
        
    def write_history(self, line):
        if line[-1] != "\n":
            line += "\n"
        self.history_file.write(line)
        self.history_file.flush()
    
    def help_commands(self):
        lines = []  # Collect lines in a list
        fs = uos.listdir("/bin")
        fs.append("run")
        fs.sort()
        line = ""
        for f in fs:
            if f not in ("__init__.py", ):
                cmd = f.split(".")[0]
                if len(line + cmd + ", ") > self.display_width:
                    lines.append(line)  # Add completed line
                    line = cmd + ", "
                else:
                    line += cmd + ", "
        if line:
            lines.append(line.rstrip(", "))  # Strip trailing comma/space
        return "\n".join(lines)

    def clear_cache(self):
        self.cache.clear()
        self.frame_history.clear()
        # self.cache.append(self.prompt_c)
        # self.current_col = 1
        
    def get_display_frame(self):
        data = {}
        frame = self.cache_to_frame()[-self.display_height:]
        data["render"] = (("status", "texts"), )
        data["frame"] = frame
        data["cursor"] = self.get_cursor_position(1)
        data["status"] = [{"s": self.stats, "c": 40, "x": 0, "y": 310, "C": C.cyan}]
        if self.loading:
#             data["render"] = (("borders", "rects"),)
#             data["borders"] = [[0, 0, 256, 127, 1], [0, 119, 256, 8, 1]]
            self.loading = False
        return data
    
    def cache_to_frame_history(self):
        self.frame_history.clear()
        width = self.display_width_with_prompt
        for n, line in enumerate(self.cache[:-1]):
            line_len = len(line)
            for i in range((line_len + width - 1) // width):  # ceil(len/width) using integer math
                start = i * width
                self.frame_history.append(line[start:start + width])
                
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
        width = self.display_width_with_prompt
        if self.scroll_row == 0:
            lines = self.cache[-self.display_height:]
            for n, line in enumerate(lines):
                if len(line) > 0:
                    line_len = len(line)
                    for i in range((line_len + width - 1) // width):  # ceil(len/width) using integer math
                        start = i * width
                        frame.append(line[start:start + width])
                        row += 1
                        if len(frame) > self.display_height:
                            frame.pop(0)
                            row -= 1
                        if n == len(lines) - 1:  # last line in cache
                            cursor_chunks = (self.current_col + width - 1) // width  # ceil(current_col/width)
                            if cursor_chunks == (i + 1):  # cursor in current line
                                self.cursor_row = row
                                self.cursor_col = self.current_col % width
                                if self.cursor_col == 0:
                                    self.cursor_col = width
                                    self.cursor_col = 0
                                    self.cursor_row += 1
                                #print("cursor_row: ", row, "cursor_col: ", self.cursor_col)
                            elif cursor_chunks < (i + 1):
                                if len(frame) >= self.display_height:
                                    self.cursor_row -= 1
                else:
                    frame.append(line)
                    row += 1
                    self.cursor_row = row
        else:
            frame_lines = []
            line = self.cache[-1]
            line_len = len(line)
            width = self.display_width_with_prompt
            for i in range((line_len + width - 1) // width):  # ceil(len/width) using integer math
                start = i * width
                frame_lines.append(line[start:start + width])
            frame = self.history_to_frame(frame_lines, self.scroll_row)
        if self.cursor_row >= self.display_height:
            self.cursor_row = self.display_height - 1
        while len(frame) < self.display_height:
            frame.append("")
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
    
    def _line_str(self):
        """Convert current line chars to string. Only allocates when needed."""
        return "".join(self._line_chars)
    
    def write_char(self, c):
        if c == "\n":
            # Flush current line to cache as string, start fresh
            # DO NOT clear _line_chars here - input_char will handle that after processing
            if self._line_chars:
                self.cache.append("".join(self._line_chars))
            self.cache.append(self.prompt_c)
        elif len(c) == 1:
            # Append to list - zero allocations (list is mutable)
            self._line_chars.append(c)
            if len(self._line_chars) > self.display_width_with_prompt:
                # Line wrapped: flush current line, start new one
                self.cache.append("".join(self._line_chars))
                self._line_chars = self._line_chars[self.display_width_with_prompt:]
                self.cache[-2] = self.cache[-2][:self.display_width_with_prompt]

        if len(self.cache) > self.cache_lines:
            self.cache.pop(0)
        self.current_row = len(self.cache) - 1
        self.current_col = len(self.prompt_c) + len(self._line_chars)  # Include prompt in cursor position

    def update_stats(self, d):
        # self.stats = "[ C%3d%%|R%3d%%:%s|D %4dK|B[%s] %3d%%]" % (d[1], d[2], ram_size(d[3]), d[6] / 1024, "C" if d[8] else "D", d[9])
        self.stats = "[  CPU:%3d%%| RAM:%3d%%|%s|%s  ]" % (d[1], d[2], ram_size(d[3]), ram_size(d[4]))
        if hasattr(self.current_shell, "update_stats"):
            self.current_shell.update_stats(d)
    
    def input_char(self, c):
        try:
            if self.session_task_id is not None and self.scheduler.exists_task(self.session_task_id):
                self.scheduler.add_task(Task.get().load(self.send_session_message, c, condition = Condition.get(), kwargs = {})) # execute cmd
            else:
                if c == "\n":
                    # Convert line chars to string for command processing
                    # Note: _line_chars only contains typed chars, NOT the prompt
                    line_str = "".join(self._line_chars)
                    cmd = line_str.strip()
                    if len(cmd) > 0:
                        if cmd.startswith("run "):
                            self.history.append(line_str)
                            self.write_history(line_str)
                            cmd = " ".join(cmd.split(" ")[1:]).strip()
                            self.scheduler.add_task(Task.get().load(self.run_script_coroutine, cmd, condition = Condition.get(), kwargs = {})) # execute cmd
                        else:
                            if self.session_task_id is not None and self.scheduler.exists_task(self.session_task_id):
                                self.scheduler.add_task(Task.get().load(self.send_session_message, line_str.strip(), condition = Condition.get(), kwargs = {})) # execute cmd
                            else:
                                self.history.append(line_str)
                                self.write_history(line_str)
                                command = cmd.split(" ")[0].strip()
                                self.scheduler.add_task(Task.get().load(self.run_coroutine, cmd, condition = Condition.get(), kwargs = {})) # execute cmd
                        # Clear input buffer after command execution
                        self._line_chars = []
                    else:
                        self._line_chars = []
                        self.cache.append(self.prompt_c)
                        self.cache_to_frame_history()
                    if len(self.history) > self.history_length:
                        self.history.pop(0)
                    self.history_idx = len(self.history)
                elif c == "\b":
                    # Backspace: delete from _line_chars (typed chars only, no prompt)
                    if self.current_col > len(self.prompt_c):
                        typed_pos = self.current_col - len(self.prompt_c) - 1
                        del self._line_chars[typed_pos]
                        self.cache[-1] = self.prompt_c + "".join(self._line_chars)
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
                elif c in ("ES", "SAVE"):
                    pass
                elif c == "Ctrl-V":
                    self.paste()
                elif len(c) == 1:
                    # Insert character into list at cursor position (relative to typed chars)
                    typed_pos = self.current_col - len(self.prompt_c)
                    self._line_chars.insert(typed_pos, c)
                    self.cache[-1] = self.prompt_c + "".join(self._line_chars)
                    self.cursor_move_right()

            if len(self.cache) > self.cache_lines:
                self.cache.pop(0)
            self.current_row = len(self.cache)
            #self.current_col = len(self.cache[-1])
        except Exception as e:
            print(sys.print_exception(e))

    def paste(self):
        line = ClipBoard.get_line()
        if line:
            typed_pos = self.current_col - len(self.prompt_c)
            # Insert all chars at once to preserve order
            self._line_chars[typed_pos:typed_pos] = list(line)
            self.cache[-1] = self.prompt_c + "".join(self._line_chars)
            self.current_col += len(line)        
            
    def write_line(self, line):
        self.cache.append(line)
        if len(self.cache) > self.cache_lines:
            self.cache.pop(0)
        self.current_row = len(self.cache) - 1
        self.current_col = len(self.cache[-1])
        self.cache_to_frame_history()
    
    def write_lines(self, lines, end = False):
        if lines:
            # Process line by line without creating N string objects from split()
            i = 0
            lines_len = len(lines)
            while i < lines_len:
                # Find next newline
                j = i
                while j < lines_len and lines[j] != "\n" and lines[j] != "\r":
                    j += 1
                line = lines[i:j]
                i = j + 1  # Skip past newline
                self.cache.append(line)
                if len(self.cache) > self.cache_lines:
                    self.cache.pop(0)
                self.current_row = len(self.cache) - 1
                self.current_col = len(self.cache[-1])
        if end:
            self.write_char("\n")
        self.cache_to_frame_history()
            
    def write(self, s):
        line_width = self.display_width_with_prompt
        i = 0
        s_len = len(s)
        while i < s_len:
            chunk = s[i:i + line_width]
            self.cache.append(chunk)
            if len(self.cache) > self.cache_lines:
                self.cache.pop(0)
            self.current_row = len(self.cache) - 1
            self.current_col = len(self.cache[-1])
            i += line_width
        self.write_char("\n")
        self.cache_to_frame_history()
            
    def run(self, task, cmd):
        yield Condition.get().load(sleep = 0, send_msgs = [
            Message.get().load({"cmd": cmd}, receiver = self.storage_id)
        ])
        
    def send_session_message(self, task, msg):
        #print("send_session_message:", msg, self.session_task_id)
        yield Condition.get().load(sleep = 0, send_msgs = [
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
        try:
            if module not in sys.modules:
                #import_str = "from bin import %s" % module
                # globals()[module] = __import__(module)
                sys.modules[module] = __import__(module) # globals()[module]
                # import_str = "import %s; sys.modules['%s'] = %s" % (module, module, module)
                # exec(import_str)
            if sys.modules[module].coroutine:
                #bin.__dict__[]
                #self.session_task_id = self.scheduler.add_task(Task(bin.__dict__[module].main, cmd, kwargs = {"args": args[1:], "shell_id": self.scheduler.shell_id, "shell": self}, need_to_clean = [bin.__dict__[module]])) # execute cmd
                self.session_task_id = self.scheduler.add_task(
                    Task.get().load(sys.modules[module].main, cmd, condition = Condition.get(), kwargs = {"args": args[1:],
                                                                                                          "shell_id": self.scheduler.current_shell_id,
                                                                                                          "shell_obj_id": self.shell_id,
                                                                                                          "display_id": self.display_id,
                                                                                                          "shell": self}, need_to_clean = [sys.modules[module]])
                ) # execute cmd
            else:
                yield Condition.get().load(sleep = 0, send_msgs = [
                    Message.get().load({"cmd": cmd}, receiver = self.storage_id)
                ])
        except Exception as e:
            buf = StringIO()
            sys.print_exception(e, buf)
            yield Condition.get().load(sleep = 0, wait_msg = False, send_msgs = [
                Message.get().load({"output": "error: %s" % buf.getvalue()}, receiver = self.scheduler.current_shell_id)
            ])

    def run_script_coroutine(self, task, cmd):
        args = cmd.split(" ")
        script_path = abs_path(args[0])
        if exists(script_path) and isfile(script_path):
            module_path, script_name = path_split(script_path)
            module = script_name.split(".")[0]
            try:
                sys.path.insert(0, module_path)
                if module not in sys.modules:
                    # globals()[module] = __import__(module)
                    sys.modules[module] = __import__(module) # globals()[module]
                    # import_str = "import bin; from bin import %s; sys.modules['%s'] = %s" % (module, module, module)
                    # exec(import_str)
                if sys.modules[module].coroutine:
                    self.session_task_id = self.scheduler.add_task(
                        Task.get().load(sys.modules[module].main, cmd, condition = Condition.get(), kwargs = {"args": args[1:],
                                                                                                              "shell_id": self.scheduler.current_shell_id,
                                                                                                              "shell_obj_id": self.shell_id,
                                                                                                              "display_id": self.display_id,
                                                                                                              "shell": self}, need_to_clean = [sys.modules[module]], reset_sys_path = True)
                    ) # execute cmd
                else:
                    sys.path.pop(0)
                    yield Condition.get().load(sleep = 0, wait_msg = False, send_msgs = [
                        Message.get().load({"output": "it's not a coroutine script!"}, receiver = self.scheduler.current_shell_id)
                    ])
            except Exception as e:
                buf = StringIO()
                sys.print_exception(e, buf)
                yield Condition.get().load(sleep = 0, wait_msg = False, send_msgs = [
                    Message.get().load({"output": "error: %s" % buf.getvalue()}, receiver = self.scheduler.current_shell_id)
                ])
        else:
            yield Condition.get().load(sleep = 0, wait_msg = False, send_msgs = [
                Message.get().load({"output": "script path not exists!"}, receiver = self.scheduler.current_shell_id)
            ])
    
    def cursor_move_left(self):
        if self.current_col > len(self.prompt_c):
            self.current_col -= 1
        #print("current_col: ", self.current_col)
    
    def cursor_move_right(self):
        if self.current_col < len(self.prompt_c) + len(self._line_chars):
            self.current_col += 1
        #print("current_col: ", self.current_col)
        
    def scroll_up(self):
        self.scroll_row -= 5 # self.display_height
        #print("scroll_row:", self.scroll_row)
        
    def scroll_down(self):
        self.scroll_row += 5 # self.display_height
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
            full_line = self.prompt_c + self.history[self.history_idx]
            self._line_chars = list(self.history[self.history_idx])  # typed chars only
            self.cache[-1] = full_line
            self.current_row = len(self.cache) - 1
            self.current_col = len(full_line)

    def history_next(self):
        self.history_idx += 1
        if self.history_idx > len(self.history) - 1:
            self.history_idx = len(self.history)
        #print("history:", self.history, self.history_idx)
        if len(self.history) > 0:
            if self.history_idx > len(self.history) - 1:
                self._line_chars = []
                self.cache[-1] = self.prompt_c
            else:
                self._line_chars = list(self.history[self.history_idx])  # typed chars only
                self.cache[-1] = self.prompt_c + self.history[self.history_idx]
            #print("history:", self.history, self.history_idx)
            self.current_row = len(self.cache) - 1
            self.current_col = len(self.cache[-1])
