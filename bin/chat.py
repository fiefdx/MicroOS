import uos
import sys
import time
from math import ceil
from io import StringIO

from lib.listfile import ListFile
from lib.shell import Shell
from lib.scheduler import Condition, Message
from lib.ollama import Chat
from lib.common import exists, path_join, isfile, isdir, mkdirs, path_split, Resource, ram_size
from lib.display import Colors as C

coroutine = True


class ChatShell(Shell):
    def __init__(self, display_size = (19, 9), cache_size = (-1, 100), history_length = 100, host = "", port = 11434, model = "llama:3.2", stream = False, prompt_c = "\x00", scheduler = None, display_id = None, storage_id = None, history_file_path = "/.cache/.chat_history", ram = True, chat_id = 0):
        self.display_width = display_size[0]
        self.display_height = display_size[1]
        self.display_width_with_prompt = display_size[0] + len(prompt_c)
        self.history_length = history_length
        self.prompt_c = prompt_c
        self.id = chat_id
        if not exists("/.cache"):
            mkdirs("/.cache")
        self.cache_path = "/.cache"
        if exists("/sd"):
            if not exists("/sd/.cache"):
                mkdirs("/sd/.cache")
            self.cache_path = "/sd/.cache"
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
        self.chat = Chat(host = host, port = port, model = model, stream = stream, cache_file = path_join(self.cache_path, "chat_request_cache.%d.txt" % self.id))
        self.chat_log = None
        self.load_history()
        # self.clear()
        
    # def clear(self):
    #     self.term = StringIO()
    #     os.dupterm(self.term)

    def set_ram(self, ram):
        self.cache = [] if ram else ListFile(path_join(self.cache_path, "chat_cache.%d.txt" % self.id), shrink_threshold = 1024000) # []
        self.frame_history = [] if ram else ListFile(path_join(self.cache_path, "chat_history_cache.%d.txt" % self.id), shrink_threshold = 1024000) # []
    
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
        if not hasattr(Resource, "chat_history_file"):
            Resource.chat_history_file = open(self.history_file_path, "a")
        self.history_file = Resource.chat_history_file
        self.history_idx = len(self.history)
    
    def _line_str(self):
        """Convert current line chars to string. Only allocates when needed."""
        return "".join(self._line_chars)
        
    def input_char(self, c):
        try:
            if c == "\n":
                line_str = self._line_str()
                cmd = line_str.strip()
                if len(cmd) > 0:
                    self.history.append(line_str)
                    self.write_history(line_str)
                    if cmd == "exit" or cmd == "quit":
                        self.exit = True
                    elif cmd == "clear":
                        self.cache.clear()
                        self.frame_history.clear()
                        self.cache.append(self.prompt_c)
                        self.current_row = len(self.cache) - 1
                        self.current_col = len(self.prompt_c)
                        self._line_chars = []
                    elif cmd == "new":
                        if self.chat_log is not None:
                            self.chat_log.close()
                        self.chat_log = None
                        self.chat.clear()
                        self.write_lines("new chat", end = True)
                    elif cmd.startswith("new:"):
                        if self.chat_log is not None:
                            self.chat_log.close()
                        name = ":".join(cmd.split(":")[1:]).strip()
                        if not exists("/sd/chat_log"):
                            mkdirs("/sd/chat_log")
                        self.chat_log = open(path_join("/sd/chat_log", name), "a")
                        self.chat.clear()
                        self.write_lines("new chat to %s" % name, end = True)
                    elif cmd == "info":
                        message = "host: %s\nport: %s\nmodel: %s\nctx: %s\n" % (self.chat.host, self.chat.port, self.chat.model, self.chat.context_length)
                        self.write_lines(message, end = True)
                    elif cmd.startswith("set model:"):
                        self.chat.model = ":".join(cmd.split(":")[1:]).strip()
                        self.write_lines("model: %s" % self.chat.model, end = True)
                    elif cmd.startswith("set ctx:"):
                        self.chat.context_length = int(cmd.split(":")[-1].strip())
                        self.write_lines("ctx: %s" % self.chat.context_length, end = True)
                    elif cmd.startswith("set host:"):
                        self.chat.host = cmd.split(":")[-1].strip()
                        self.write_lines("host: %s" % self.chat.host, end = True)
                    elif cmd.startswith("set port:"):
                        self.chat.port = cmd.split(":")[-1].strip()
                        self.write_lines("port: %s" % self.chat.port, end = True)
                    elif cmd == "models":
                        success, models = self.chat.models()
                        if success:
                            lines = ""
                            for name in models:
                                lines += name + "\n"
                            if lines.endswith("\n"):
                                lines = lines[:-1]
                        else:
                            lines = models
                        self.write_lines(lines, end = True)
                    else:
                        try:
                            success, content = self.chat.chat(cmd)
                            if success:
                                if self.chat_log:
                                    self.chat_log.write("Q: " + cmd + "\n")
                                    self.chat_log.write("A: " + content + "\n\n")
                                    self.chat_log.flush()
                                self.write_lines(content + "\n", end = True)
                            else:
                                self.write_lines("fail reason: %s" % content.decode(), end = True)
                        except Exception as e:
                            self.write_lines(str(e), end = True)
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
        except Exception as e:
            buf = StringIO()
            sys.print_exception(e, buf)
            reason = buf.getvalue()
            self.write_lines("error: %s" % str(reason), end = True)
        
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

    def get_using_ram_frame(self):
        msg = "         Use RAM or not? [y/n]"
        self.cursor_col = len(msg)
        self.cursor_row = 2
        return ["", "", msg, "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""]

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
            # data["borders"] = [] # [[0, 0, 256, 127, 1], [0, 119, 256, 8, 1]]
            self.loading = False
        return data

    def close(self):
        if hasattr(self.cache, 'close'):
            self.cache.close()
        if hasattr(self.frame_history, 'close'):
            self.frame_history.close()


def main(*args, **kwargs):
    task = args[0]
    name = args[1]
    shell = kwargs["shell"]
    shell_id = kwargs["shell_id"]
    shell_obj_id = kwargs["shell_obj_id"]
    display_id = shell.display_id
    shell.disable_output = True
    try:
        model = "llama3.2"
        host = "192.168.4.30"
        port = 11434
        stream = False
        if len(kwargs["args"]) > 0:
            host = kwargs["args"][0]
        if len(kwargs["args"]) > 1:
            port = kwargs["args"][1]
        if len(kwargs["args"]) > 2:
            stream = True if int(kwargs["args"][2]) == 1 else False
        s = ChatShell(display_size = (39, 28), host = host, port = port, model = model, stream = stream, chat_id = shell_obj_id)
        shell.current_shell = s
        yield Condition.get().load(sleep = 0, wait_msg = True, send_msgs = [
            Message.get().load({"frame": s.get_using_ram_frame(), "cursor": s.get_cursor_position(1)}, receiver = display_id)
        ])
        msg = task.get_message()
        c = msg.content["msg"]
        msg.release()
        if c == "y" or c == "Y" or c == "\n":
            s.set_ram(True)
        else:
            s.set_ram(False)
        s.write_line("             Welcome to Chat")
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
        s.close()
        shell.disable_output = False
        shell.current_shell = None
        shell.loading = True
        s.cache = None
        s.history = None
        s.frame_history = None
        del s
        yield Condition.get().load(sleep = 0, wait_msg = False, send_msgs = [
            Message.get().load({"output": "quit from chat"}, receiver = shell_id)
        ])
    except Exception as e:
        shell.disable_output = False
        shell.current_shell = None
        shell.loading = True
        yield Condition.get().load(sleep = 0, send_msgs = [
            Message.get().load({"output": str(e)}, receiver = shell_id)
        ])
