import os
import gc
import re
import sys
import time
import random
from math import ceil
from io import StringIO

from lib.listfile import ListFile
from lib.shell import Shell
from lib.scheduler import Condition, Message
from lib.ollama import Chat
from lib.common import exists, path_join, isfile, isdir, mkdirs, ClipBoard, abs_path
from lib.display import Colors as C
from lib.analyzer import tokenize
from lib.analyzer import TOKEN_KEYWORD, TOKEN_IDENT, TOKEN_NUMBER, TOKEN_STRING, TOKEN_COMMENT, TOKEN_OP, TOKEN_WS

coroutine = True


class EditShell(object):
    TOKEN_COLORS = {
        TOKEN_KEYWORD: C.red,
        TOKEN_STRING: C.yellow,
        TOKEN_OP: C.magenta,
        TOKEN_COMMENT: C.blue,
        TOKEN_NUMBER: C.cyan,
    }

    def __init__(self, file_path, display_size = (40, 29), cache_size = 28, ram = True, edit_id = 0):
        self.display_width = display_size[0]
        self.display_height = display_size[1]
        self.offset_col = 0
        self.cache_size = cache_size
        self.id = edit_id
        if not exists("/.cache"):
            mkdirs("/.cache")
        self.cache_path = "/.cache"
        if exists("/sd"):
            if not exists("/sd/.cache"):
                mkdirs("/sd/.cache")
            self.cache_path = "/sd/.cache"
        self.cache = []
        self.edit_history = []
        self.edit_redo_cache = []
        self.edit_history_max_length = 1000
        self.edit_last_line = None
        self.cursor_color = 1
        self.cursor_row = 0
        self.cursor_col = 0
        self.enable_cursor = True
        self.exit = False
        self.file_path = file_path
        self.total_lines = 0
        self.line_num = 0
        self.display_offset_row = 0
        self.display_offset_col = 0
        if not exists(self.file_path):
            f = open(self.file_path, "w")
            f.close()
        self.status = "loading"
        self.mode = "edit"
        self.previous_mode = "edit"
        self.select_start_row = 0
        self.select_start_col = 0
        self.exit_count = 0
        self.chat = Chat(host = "", port = 11434, model = "llama3.2:1b", cache_file = path_join(self.cache_path, ".chat.cache.%d.txt" % self.id))
        self.highlight = self.file_path.endswith(".py")
        self.frame_previous = None
        self.frame_force_update = False
        self.previous_offset_row = 0
        self.previous_offset_col = 0
        self.highlight_cache = {}
        # Reusable lists to reduce memory allocations
        self._clear_lines = []
        self._select_lines = []
        
    def set_ram(self, ram):
        self.cache = [] if ram else ListFile(path_join(self.cache_path, "edit_cache.%d.json" % self.id), shrink_threshold = 1024000) # []
        time.sleep_ms(100)
        self.edit_history = [] if ram else ListFile(path_join(self.cache_path, "edit_history_cache.%d.json" % self.id), shrink_threshold = 1024000) # []
        time.sleep_ms(100)
        self.edit_redo_cache = [] if ram else ListFile(path_join(self.cache_path, "edit_redo_cache.%d.json" % self.id), shrink_threshold = 1024000) # []
        
    def input_char(self, c):
        if c == "refresh":
            self.frame_force_update = True
        if self.mode == "edit":
            if len(self.cache) == 0:
                self.cache.append("")
            if c == "\n":
                self.status = "changed"
                self.exit_count = 0
                before_enter = self.cache[self.cursor_row][:self.cursor_col + self.offset_col]
                after_enter = self.cache[self.cursor_row][self.cursor_col + self.offset_col:]
                col = 0
                if self.highlight:
                    tokens = tokenize(before_enter)
                    if len(tokens) > 1:
                        if tokens[0][0] == TOKEN_WS and tokens[0][1].isspace():
                            col += len(tokens[0][1])
                        if tokens[-1][0] == TOKEN_OP and tokens[-1][1] in (":", "(", "[", "{"):
                            col += 4
                        after_enter = " " * col + after_enter
                    elif len(tokens) > 0:
                        if tokens[0][0] == TOKEN_WS and tokens[0][1].isspace():
                            after_enter = tokens[0][1] + after_enter
                            col += len(tokens[0][1])
                self.cache[self.cursor_row] = before_enter
                self.edit_last_line = self.cursor_row
                self.cursor_row += 1
                op = None
                if len(self.cache) > self.cursor_row:
                    self.cache.insert(self.cursor_row, after_enter)
                    op = ["insert", self.cursor_row - 1, before_enter, after_enter]
                else:
                    self.cache.append(after_enter)
                    op = ["append", self.cursor_row - 1, before_enter, after_enter]
                self.edit_redo_cache.clear()
                if self.cursor_row > self.display_offset_row + self.cache_size - 1:
                    self.display_offset_row += 1
                self.cursor_col = 0
                self.offset_col = 0
                op.append((self.cursor_col, self.cursor_row, self.display_offset_col, self.display_offset_row, self.offset_col))
                self.edit_history.append(op)
                if col > 0:
                    self.cursor_move_right(col)
                self.frame_force_update = True
                if self.highlight:
                    self.highlight_cache.clear()
            elif c == "\b":
                self.status = "changed"
                self.exit_count = 0
                op = None
                if len(self.cache[self.cursor_row]) == 0:
                    self.edit_last_line = self.cursor_row
                    self.edit_redo_cache.clear()
                    self.cache.pop(self.cursor_row)
                    self.cursor_move_left()
                    self.edit_history.append(["delete", self.cursor_row, "", (self.cursor_col, self.cursor_row, self.display_offset_col, self.display_offset_row, self.offset_col)])
                else:
                    delete_before = self.cache[self.cursor_row][:self.cursor_col + self.offset_col]
                    if len(delete_before) > 0:
                        self.append_edit_operation()
                        self.cache[self.cursor_row] = self.cache[self.cursor_row][:self.cursor_col + self.offset_col - 1] + self.cache[self.cursor_row][self.cursor_col + self.offset_col:]
                        self.cursor_move_left()
                    else:
                        self.append_edit_operation()
                        if self.cursor_row > 0:
                            self.edit_last_line = self.cursor_row
                            current_line = self.cache.pop(self.cursor_row)
                            op = ["merge", self.cursor_row, current_line, "", (self.cursor_col, self.cursor_row, self.display_offset_col, self.display_offset_row, self.offset_col)]
                            self.edit_redo_cache.clear()
                            self.cursor_move_left()
                            op[3] = self.cache[self.cursor_row]
                            self.cache[self.cursor_row] += current_line
                            self.edit_history.append(op)
                self.frame_force_update = True
                if self.highlight:
                    self.highlight_cache.clear()
            elif c == "UP" or c == "SUP":
                self.cursor_move_up()
            elif c == "DN" or c == "SDN":
                self.cursor_move_down()
            elif c in ("BX"):
                self.page_up()
            elif c in ("BB"):
                self.page_down()
            elif c == "LT":
                self.cursor_move_left()
            elif c == "RT":
                self.cursor_move_right()
            elif c == "BY":
                self.page_left()
            elif c == "BA":
                self.page_right()
            elif c == "SAVE":
                fp = open(self.file_path, "w")
                for line in self.cache:
                    fp.write(line + "\n")
                fp.close()
                self.status = "saved"
                self.frame_force_update = True
            elif c == "Ctrl-A":
                self.redo()
                self.frame_force_update = True
            elif c == "Ctrl-Z":
                self.undo()
                self.frame_force_update = True
            elif c == "Ctrl-B":
                self.mode = "select"
                self.select_start_row = self.cursor_row
                self.select_start_col = self.cursor_col + self.offset_col
                self.frame_force_update = True
            elif c == "Ctrl-V":
                self.paste()
                self.frame_force_update = True
            elif c == "Ctrl-Q":
                self.generate_with_chat()
                self.frame_force_update = True
            elif c == "Ctrl-G":
                self.mode = "goto"
                self.goto_str = ""
                self.frame_force_update = True
            elif c == "Ctrl-/":
                if self.comment_one_line():
                    self.status = "changed"
                    self.exit_count = 0
                    self.frame_force_update = True
            elif c == "ES":
                if self.status == "saved":
                    self.exit = True
                else:
                    self.exit_count += 1
                    if self.exit_count >= 3:
                        self.exit = True
            elif len(c) == 1:
                self.status = "changed"
                self.exit_count = 0
                self.append_edit_operation()
                n = 1
                if c == "\t":
                    c = "    "
                    n = 4
                self.cache[self.cursor_row] = self.cache[self.cursor_row][:self.cursor_col + self.offset_col] + c + self.cache[self.cursor_row][self.cursor_col + self.offset_col:]
                self.cursor_move_right(n)
                self.frame_force_update = True
                if self.highlight:
                    self.highlight_cache.clear()
        elif self.mode == "select":
            if c == "UP" or c == "SUP":
                self.cursor_move_up()
            elif c == "DN" or c == "SDN":
                self.cursor_move_down()
            elif c in ("BX"):
                self.page_up()
            elif c in ("BB"):
                self.page_down()
            elif c == "LT":
                self.cursor_move_left()
            elif c == "RT":
                self.cursor_move_right()
            elif c == "BY":
                self.page_left()
            elif c == "BA":
                self.page_right()
            elif c == "Ctrl-C":
                self.previous_mode = self.mode
                self.mode = "edit"
                self.copy_into_clipboard()
            elif c == "Ctrl-X":
                self.previous_mode = self.mode
                self.mode = "edit"
                self.copy_into_clipboard(cut = True)
            elif c == "Ctrl-/":
                self.comment_select_lines()
            elif c == "ES":
                self.previous_mode = self.mode
                self.mode = "edit"
            self.frame_force_update = True
        elif self.mode == "goto":
            if c.isdigit():
                self.goto_str += c
            elif c == "\b":
                if len(self.goto_str) > 0:
                    self.goto_str = self.goto_str[:-1]
            elif c == "\n":
                self.previous_mode = self.mode
                self.mode = "edit"
                if len(self.goto_str) > 0:
                    self.goto(int(self.goto_str))
            elif c == "ES":
                self.previous_mode = self.mode
                self.mode = "edit"
            self.frame_force_update = True

    def append_edit_operation(self):
        if self.cursor_row != self.edit_last_line:
            if self.edit_last_line is not None:
                self.edit_history.append(["edit", self.edit_last_line, self.cache[self.edit_last_line], (self.cursor_col, self.cursor_row, self.display_offset_col, self.display_offset_row, self.offset_col)])
                if len(self.edit_history) > self.edit_history_max_length:
                    self.edit_history.pop(0)
            self.edit_last_line = self.cursor_row
            self.edit_history.append(["edit", self.edit_last_line, self.cache[self.edit_last_line], (self.cursor_col, self.cursor_row, self.display_offset_col, self.display_offset_row, self.offset_col)])
            if len(self.edit_history) > self.edit_history_max_length:
                self.edit_history.pop(0)
        else:
            self.edit_history.append(["edit", self.edit_last_line, self.cache[self.edit_last_line], (self.cursor_col, self.cursor_row, self.display_offset_col, self.display_offset_row, self.offset_col)])
            if len(self.edit_history) > self.edit_history_max_length:
                self.edit_history.pop(0)
        self.edit_redo_cache.clear()
        
    def load_and_calc_total_lines(self):
        n = 0
        self.file = open(self.file_path, "r")
        self.file.seek(0, 2)
        size = self.file.tell()
        yield 0
        self.file.seek(0)
        pos = self.file.tell()
        line = self.file.readline()
        while line:
            line = line.replace("\r", "")
            line = line.replace("\n", "")
            self.cache.append(line)
            n += 1
            if n % 100 == 0:
                gc.collect()
            pos = self.file.tell()
            line = self.file.readline()
            if n % 10 == 0:
                yield int(pos * 100 / size)
        self.total_lines = n
        self.file.close()
        self.status = "saved"
        yield 100
        gc.collect()
        
    def exists_line(self, line_num):
        return line_num >= 0 and line_num < self.total_lines
    
    def highlight_line(self, line, start, end, row):
        result = []
        for token in tokenize(line):
            if token[0] in EditShell.TOKEN_COLORS:
                c = EditShell.TOKEN_COLORS[token[0]]
                key = token[1]
                ks = token[2]
                ke = token[3]
                if ks >= start and ke <= end:
                    result.append({"s": key, "c": " ", "x": (ks - start) * 8, "y": row * 11 + 1, "C": c})
                elif ks < start and ke > start:
                    key = key[start - ks:]
                    result.append({"s": key, "c": " ", "x": 0, "y": row * 11 + 1, "C": c})
                elif ks < end and ke > end:
                    key = key[:-(ke - end)]
                    result.append({"s": key, "c": " ", "x": (ks - start) * 8, "y": row * 11 + 1, "C": c})
        return result

    def get_frame(self):
        frame, highlights = self.cache_to_frame()
        status = "{progress: <25}{mode: >8}{status: >7}".format(
            progress = "%s/%s/%s" % (self.cursor_col + self.offset_col, self.cursor_row + 1, len(self.cache)),
            mode = "% 7s " % self.mode,
            status = self.status,
        )
        data = {
            "cursor": self.get_cursor_position(1),
            "render": (("clear_lines", "lines"), ("selects", "lines"), ("highlights", "texts"), ("status_bottom", "texts")),
            "clear_lines": [],
            "selects": [],
            "highlights": [],
            "status_bottom": [{"s": status, "c": 40, "x": 0, "y": 28 * 11 + 1, "C": C.cyan}]
        }
        if frame is not None:
            data["frame"] = frame
        if highlights is not None:
            data["highlights"] = highlights
        
        if self.mode == "select":
            self._clear_lines.clear()
            for i in range(28):
                self._clear_lines.append([1, i * 11 + 9, 318, i * 11 + 9, C.black])
            self._select_lines.clear()
            for l in self.get_select_lines():
                self._select_lines.append([l[0][0], l[0][1], l[1][0] - 1, l[1][1], C.red])
            data["clear_lines"] = self._clear_lines
            data["selects"] = self._select_lines
        elif self.previous_mode == "select":
            self.previous_mode = self.mode
            self._clear_lines.clear()
            for i in range(28):
                self._clear_lines.append([1, i * 11 + 9, 318, i * 11 + 9, C.black])
            data["clear_lines"] = self._clear_lines
        return data
    
    def get_using_ram_frame(self):
        msg = "         Use RAM or not? [y/n]"
        self.cursor_col = len(msg)
        self.cursor_row = 2
        return ["", "", msg, "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""]

    def get_loading_frame(self, p):
        msg = "loading: %s%%" % p
        self.cursor_col = len(msg)
        self.cursor_row = 28
        if p == 100:
            self.cursor_row = 0
            self.cursor_col = 0
        return ["", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", msg]
            
    def need_update_frame(self):
        if self.frame_previous is None:
            return True
        if self.frame_force_update:
            self.frame_force_update = False
            return True
        if self.display_offset_row != self.previous_offset_row or self.offset_col != self.previous_offset_col:
            return True
        return False
    
    def cache_to_frame(self):
        frame = []
        highlights = []
        if self.need_update_frame():
            for n, line in enumerate(self.cache[self.display_offset_row: self.display_offset_row + self.cache_size]):
                frame.append(line[self.offset_col: self.offset_col + self.display_width])
                if self.highlight:
                    line_num = self.display_offset_row + n
                    if line_num not in self.highlight_cache:
                        self.highlight_cache[line_num] = self.highlight_line(line, self.offset_col, self.offset_col + self.display_width, n)
                    highlights.extend(self.highlight_cache[line_num])
            for i in range(self.cache_size - len(frame)):
                frame.append("")
            self.frame_previous = True
            self.previous_offset_row = self.display_offset_row
            self.previous_offset_col = self.offset_col
            return frame, highlights
        else:
            return None, None
    
    def get_cursor_position(self, c = None):
        return self.cursor_col, self.cursor_row - self.display_offset_row, self.cursor_color if c is None else c
    
    def set_cursor_color(self, c):
        self.cursor_color = c

    def cr2xy(self, col, row):
        return (col * 8 + 1, row * 11 + 9)

    def paste(self):
        n = 0
        insert_col = self.cursor_col + self.offset_col
        insert_row = self.cursor_row
        original_line = self.cache[insert_row]
        for line in ClipBoard.iter_lines():
            if n == 0:
                self.cache[insert_row] = self.cache[insert_row][:insert_col] + line
                if line.endswith("\n"):
                    self.edit_history.append(["edit", insert_row, self.cache[insert_row], (self.cursor_col, self.cursor_row, self.display_offset_col, self.display_offset_row, self.offset_col)])
                    self.cache[insert_row] = self.cache[insert_row][:-1]
                    self.edit_history.append(["insert_row", insert_row + 1, "", (self.cursor_col, self.cursor_row, self.display_offset_col, self.display_offset_row, self.offset_col)])
                    self.cache.insert(insert_row + 1, "")
            else:
                self.edit_history.append(["edit", insert_row + n, self.cache[insert_row + n], (self.cursor_col, self.cursor_row, self.display_offset_col, self.display_offset_row, self.offset_col)])
                self.cache[insert_row + n] = line
                if line.endswith("\n"):
                    self.edit_history.append(["edit", insert_row + n, self.cache[insert_row + n], (self.cursor_col, self.cursor_row, self.display_offset_col, self.display_offset_row, self.offset_col)])
                    self.cache[insert_row + n] = self.cache[insert_row + n][:-1]
                    self.edit_history.append(["insert_row", insert_row + n + 1, "", (self.cursor_col, self.cursor_row, self.display_offset_col, self.display_offset_row, self.offset_col)])
                    self.cache.insert(insert_row + n + 1, "")
            n += 1
        if n > 0:
            self.cursor_col = len(self.cache[insert_row + n - 1])
            self.offset_col = int(self.cursor_col / self.display_width) * self.display_width
            self.cursor_col = self.cursor_col % self.display_width
            self.cache[insert_row + n - 1] += original_line[insert_col + 1:]
            self.cursor_row = insert_row + n - 1
            if self.cursor_row - self.display_offset_row >= self.cache_size:
                self.display_offset_row = self.cursor_row - self.cache_size + 1

    def copy_into_clipboard(self, cut = False):
        display_start = self.display_offset_row
        display_end = self.display_offset_row + self.cache_size
        select_start_col = self.select_start_col
        select_start_row = self.select_start_row
        select_end_col = self.cursor_col + self.offset_col
        select_end_row = self.cursor_row
        if select_start_row > select_end_row or (select_start_row == select_end_row and select_start_col > select_end_col):
            select_end_col = self.select_start_col
            select_end_row = self.select_start_row
            select_start_col = self.cursor_col + self.offset_col
            select_start_row = self.cursor_row
        if select_start_row == select_end_row:
            if select_start_col != select_end_col:
                ClipBoard.set(self.cache[select_start_row][select_start_col: select_end_col + 1])
                if cut:
                    self.cache[select_start_row] = self.cache[select_start_row][:select_start_col] + self.cache[select_start_row][select_end_col + 1:]
        else:
            fp = ClipBoard.get_file()
            fp.write(self.cache[select_start_row][select_start_col:] + "\n")
            for row in range(select_start_row + 1, select_end_row):
                fp.write(self.cache[row] + "\n")
            fp.write(self.cache[select_end_row][:select_end_col])
            fp.close()
            if cut:
                self.edit_redo_cache.clear()
                if select_start_col == 0:
                    start_delete = select_start_row
                else:
                    start_delete = select_start_row + 1
                    self.edit_history.append(["edit", select_start_row, self.cache[select_start_row], (self.cursor_col, self.cursor_row, self.display_offset_col, self.display_offset_row, self.offset_col)])
                    self.cache[select_start_row] = self.cache[select_start_row][:select_start_col]
                    self.edit_history.append(["edit", select_start_row, self.cache[select_start_row], (self.cursor_col, self.cursor_row, self.display_offset_col, self.display_offset_row, self.offset_col)])
                for row in range(start_delete, select_end_row):
                    self.edit_history.append(["delete", start_delete, self.cache[start_delete], (self.cursor_col, self.cursor_row, self.display_offset_col, self.display_offset_row, self.offset_col)])
                    self.cache.pop(start_delete)
                self.edit_history.append(["edit", start_delete, self.cache[start_delete], (self.cursor_col, self.cursor_row, self.display_offset_col, self.display_offset_row, self.offset_col)])
                self.cache[start_delete] = self.cache[start_delete][select_end_col:]

    def get_select_lines(self):
        lines = []
        display_start = self.display_offset_row
        display_end = self.display_offset_row + self.cache_size
        select_start_col = self.select_start_col
        select_start_row = self.select_start_row
        select_end_col = self.cursor_col + self.offset_col
        select_end_row = self.cursor_row
        if select_start_row > select_end_row or (select_start_row == select_end_row and select_start_col > select_end_col):
            select_end_col = self.select_start_col
            select_end_row = self.select_start_row
            select_start_col = self.cursor_col + self.offset_col
            select_start_row = self.cursor_row
        if select_start_row >= display_start and select_end_row < display_end:
            if select_start_row == select_end_row:
                if select_start_col != select_end_col:
                    line = []
                    if select_start_col >= self.offset_col:
                        line.append(self.cr2xy(select_start_col - self.offset_col, select_start_row - display_start))
                    else:
                        line.append(self.cr2xy(0, select_start_row - display_start))
                    line.append(self.cr2xy(select_end_col - self.offset_col, select_start_row - display_start))
                    lines.append(line)
            else:
                line = []
                if select_start_col >= self.offset_col:
                    line.append(self.cr2xy(select_start_col - self.offset_col, select_start_row - display_start))
                else:
                    line.append(self.cr2xy(0, select_start_row - display_start))
                line.append(self.cr2xy(self.display_width, select_start_row - display_start))
                lines.append(line)
                for row in range(select_start_row + 1, select_end_row):
                    lines.append([self.cr2xy(0, row - display_start), self.cr2xy(self.display_width, row - display_start)])
                if select_end_col - self.offset_col > 0:
                    line = [self.cr2xy(0, select_end_row - display_start)]
                    line.append(self.cr2xy(select_end_col - self.offset_col, select_end_row - display_start))
                    lines.append(line)
        elif select_start_row >= display_start and select_end_row >= display_end:
            line = []
            if select_start_col >= self.offset_col:
                line.append(self.cr2xy(select_start_col - self.offset_col, select_start_row - display_start))
            else:
                line.append(self.cr2xy(0, select_start_row - display_start))
            line.append(self.cr2xy(self.display_width, select_start_row - display_start))
            lines.append(line)
            for row in range(select_start_row + 1, display_end):
                lines.append([self.cr2xy(0, row - display_start), self.cr2xy(self.display_width, row - display_start)])
        elif select_start_row < display_start and select_end_row >= display_start:
            for row in range(display_start, select_end_row):
                lines.append([self.cr2xy(0, row - display_start), self.cr2xy(self.display_width, row - display_start)])
            if select_end_col - self.offset_col > 0:
                line = [self.cr2xy(0, select_end_row - display_start)]
                line.append(self.cr2xy(select_end_col - self.offset_col, select_end_row - display_start))
                lines.append(line)
        return lines
    
    def comment_select_lines(self):
        result = False
        display_start = self.display_offset_row
        display_end = self.display_offset_row + self.cache_size
        select_start_col = self.select_start_col
        select_start_row = self.select_start_row
        select_end_col = self.cursor_col + self.offset_col
        select_end_row = self.cursor_row
        if select_start_row > select_end_row or (select_start_row == select_end_row and select_start_col > select_end_col):
            select_end_col = self.select_start_col
            select_end_row = self.select_start_row
            select_start_col = self.cursor_col + self.offset_col
            select_start_row = self.cursor_row
        if select_start_row == select_end_row:
            if select_start_col != select_end_col:
                result = self.comment_one_line(select_start_row)
        else:
            uncomments = 0
            comments = 0
            less_indent = None
            for row in range(select_start_row, select_end_row + 1):
                line = self.cache[row]
                if line != "":
                    for n, c in enumerate(line):
                        if c == " ":
                            continue
                        if c == "#":
                            if less_indent is None:
                                less_indent = n
                            else:
                                if n < less_indent:
                                    less_indent = n
                            comments += 1
                            break
                        else:
                            if less_indent is None:
                                less_indent = n
                            else:
                                if n < less_indent:
                                    less_indent = n
                            uncomments += 1
                            break
            for row in range(select_start_row, select_end_row + 1):
                line = self.cache[row]
                if line != "":
                    for n, c in enumerate(line):
                        if uncomments > 0: # need to do comments
                            self.cache[row] = self.cache[row][:less_indent] + "# " + self.cache[row][less_indent:]
                            result = True
                            break
                        else: # need to do uncomments
                            if c == " ":
                                continue
                            if c == "#":
                                d = 1
                                if len(line) - 1 > n and line[n + 1] == " ":
                                    d += 1
                                self.cache[row] = self.cache[row][:n] + self.cache[row][n+d:]
                                result = True
                                break
        return result
            
    def generate_with_chat(self):
        question = self.cache[self.cursor_row]
        for i in range(4):
            cmd = self.cache[i]
            if cmd.startswith("# set model:"):
                self.chat.model = ":".join(cmd.split(":")[1:]).strip()
            elif cmd.startswith("# set ctx:"):
                self.chat.context_length = int(cmd.split(":")[-1].strip())
            elif cmd.startswith("# set host:"):
                self.chat.host = cmd.split(":")[-1].strip()
            elif cmd.startswith("# set port:"):
                self.chat.port = cmd.split(":")[-1].strip()
        try:
            success, answer = self.chat.chat(question)
            if success:
                self.cache.insert(self.cursor_row + 1, ">>>")
                self.cache.insert(self.cursor_row + 2, "<<<")
                lines = answer.split("\n")
                for i in range(len(lines)):
                    line = lines[-i - 1]
                    if line.endswith("\n"):
                        line = line[:-1]
                    self.cache.insert(self.cursor_row + 2, line)
            else:
                self.cache.insert(self.cursor_row + 1, "fail reason: %s" % answer.decode())
        except Exception as e:
            self.cache.insert(self.cursor_row + 1, str(e))
            
    def goto(self, line_num):
        line_num -= 1
        last_line_num = len(self.cache) - 1
        if line_num < 0:
            line_num = 0
        if line_num > last_line_num:
            line_num = last_line_num
        self.cursor_col = 0
        self.cursor_row = line_num
        self.offset_col = 0
        self.display_offset_row = line_num - self.cache_size + 1
        if self.display_offset_row < 0:
            self.display_offset_row = 0
        if self.display_offset_row > len(self.cache) - self.cache_size:
            self.display_offset_row = len(self.cache) - self.cache_size
            
    def comment_one_line(self, cursor_row = None):
        result = False
        if cursor_row is None:
            cursor_row = self.cursor_row
        line = self.cache[cursor_row]
        if line != "":
            for n, c in enumerate(line):
                if c == " ":
                    continue
                if c == "#":
                    d = 1
                    if len(line) - 1 > n and line[n + 1] == " ":
                        d += 1
                    self.cache[cursor_row] = self.cache[cursor_row][:n] + self.cache[cursor_row][n+d:]
                    result = True
                    break
                else:
                    self.cache[cursor_row] = self.cache[cursor_row][:n] + "# " + self.cache[cursor_row][n:]
                    result = True
                    break
        return result

    def cursor_move_up(self):
        self.cursor_row -= 1
        if self.cursor_row < 0:
            self.cursor_row = 0
        if self.cursor_row < self.display_offset_row:
            self.display_offset_row = self.cursor_row
            if self.highlight:
                self.highlight_cache.clear()
        if len(self.cache[self.cursor_row]) < self.offset_col + self.cursor_col:
            self.cursor_col = len(self.cache[self.cursor_row]) - self.offset_col
    
    def cursor_move_down(self):
        self.cursor_row += 1
        if self.cursor_row >= len(self.cache):
            self.cursor_row = len(self.cache) - 1
        if self.cursor_row > self.display_offset_row + self.cache_size - 1:
            self.display_offset_row += 1
            if self.highlight:
                self.highlight_cache.clear()
        if len(self.cache[self.cursor_row]) < self.offset_col + self.cursor_col:
            self.cursor_col = len(self.cache[self.cursor_row]) - self.offset_col
            
    def page_up(self):
        self.display_offset_row -= self.cache_size // 4
        self.cursor_row -= self.cache_size // 4
        if self.display_offset_row < 0:
            self.display_offset_row = 0
        if self.cursor_row < 0:
            self.cursor_row = 0
        if len(self.cache[self.cursor_row]) < self.offset_col + self.cursor_col:
            self.cursor_col = len(self.cache[self.cursor_row]) - self.offset_col
        if self.highlight:
            self.highlight_cache.clear()
    
    def page_down(self):
        self.display_offset_row += self.cache_size // 4
        self.cursor_row += self.cache_size // 4
        if self.cursor_row >= len(self.cache):
            self.cursor_row = len(self.cache) - 1
        if self.display_offset_row > len(self.cache) - self.cache_size:
            self.display_offset_row = len(self.cache) - self.cache_size
        if len(self.cache[self.cursor_row]) < self.offset_col + self.cursor_col:
            self.cursor_col = len(self.cache[self.cursor_row]) - self.offset_col
        if self.highlight:
            self.highlight_cache.clear()
    
    def cursor_move_left(self):
        self.cursor_col -= 1
        if len(self.cache) > self.cursor_row:
            if len(self.cache[self.cursor_row]) >= self.offset_col:
                if self.cursor_col < 0:
                    self.cursor_col = 0
                    if self.offset_col > 0:
                        self.offset_col -= 1
                        if self.highlight:
                            self.highlight_cache.clear()
    #                     self.cache_to_frame()
                    else:
                        if self.cursor_row > 0:
                            self.cursor_row -= 1
                            self.cursor_col = len(self.cache[self.cursor_row]) % self.display_width
                            self.offset_col = len(self.cache[self.cursor_row]) - self.cursor_col
                            if self.highlight:
                                self.highlight_cache.clear()
                        else:
                            self.cursor_col = 0
                            self.offset_col = 0
            else:
                if self.cursor_col + self.offset_col <= 0:
                    self.cursor_col = -self.offset_col
        else:
            self.cursor_row = len(self.cache) - 1
            if self.cursor_row >= 0:
                self.cursor_col = len(self.cache[self.cursor_row]) % self.display_width
                self.offset_col = len(self.cache[self.cursor_row]) - self.cursor_col
                if self.highlight:
                    self.highlight_cache.clear()
            else:
                self.cursor_col = 0
                self.offset_col = 0

        if self.cursor_row < self.display_offset_row:
            self.display_offset_row = self.cursor_row
            if self.highlight:
                self.highlight_cache.clear()
        
    def cursor_move_right(self, n = 1):
        self.cursor_col += n
        if len(self.cache[self.cursor_row]) > self.cursor_col + self.offset_col - 1:
            if self.cursor_col >= self.display_width:
                self.offset_col += n
                if self.highlight:
                    self.highlight_cache.clear()
#                 self.cache_to_frame()
                self.cursor_col = self.display_width - 1
        else:
            self.cursor_col -= n
            if len(self.cache) - n > self.cursor_row:
                self.cursor_row += 1
                self.cursor_col = 0
                self.offset_col = 0
                if self.highlight:
                    self.highlight_cache.clear()
        if self.cursor_row > self.display_offset_row + self.cache_size - 1:
            self.display_offset_row += 1
            if self.highlight:
                self.highlight_cache.clear()
            
    def page_left(self):
        if self.offset_col > 0:
            self.offset_col -= self.display_width // 4
            # self.cursor_col += self.display_width // 4
            if self.offset_col < 0:
                self.offset_col = 0
            if len(self.cache[self.cursor_row]) < self.offset_col:
                self.cursor_col = len(self.cache[self.cursor_row]) - self.offset_col
            else:
                if len(self.cache[self.cursor_row]) < self.cursor_col + self.offset_col:
                    self.cursor_col = len(self.cache[self.cursor_row]) - self.offset_col
                if self.cursor_col < 0:
                    self.cursor_col = 0
            if self.highlight:
                self.highlight_cache.clear()
        elif self.offset_col == 0:
            self.cursor_col = 0
    
    def page_right(self):
        self.offset_col += self.display_width // 4
        if len(self.cache[self.cursor_row]) < self.cursor_col + self.offset_col:
            self.cursor_col = len(self.cache[self.cursor_row]) - self.offset_col
        if self.highlight:
            self.highlight_cache.clear()

    def undo(self):
        if len(self.edit_history) > 0:
            if len(self.edit_redo_cache) == 0:
                op = self.edit_history[-1]
                if op[0] == "edit":
                    if self.cache[op[1]] != op[2]:
                        self.edit_redo_cache.append(["edit", op[1], self.cache[op[1]], (self.cursor_col, self.cursor_row, self.display_offset_col, self.display_offset_row, self.offset_col)])
            op = self.edit_history.pop(-1)
            if op[0] == "edit":
                self.cache[op[1]] = op[2]
                self.cursor_col, self.cursor_row, self.display_offset_col, self.display_offset_row, self.offset_col = op[3]
            elif op[0] == "insert":
                self.cache[op[1]] = op[2] + op[3]
                self.cache.pop(op[1] + 1)
                self.cursor_col, self.cursor_row, self.display_offset_col, self.display_offset_row, self.offset_col = op[4]
                self.cursor_row -= 1
                self.cursor_col = len(op[2])
            elif op[0] == "append":
                self.cache[op[1]] = op[2] + op[3]
                self.cache.pop(op[1] + 1)
                self.cursor_col, self.cursor_row, self.display_offset_col, self.display_offset_row, self.offset_col = op[4]
                self.cursor_row -= 1
                self.cursor_col = len(op[2])
            elif op[0] == "insert_row":
                self.cache.pop(op[1])
                self.cursor_col, self.cursor_row, self.display_offset_col, self.display_offset_row, self.offset_col = op[3]
                self.cursor_row -= 1
                self.cursor_col = len(op[2])
            elif op[0] == "delete":
                self.cache.insert(op[1], op[2])
                self.cursor_col, self.cursor_row, self.display_offset_col, self.display_offset_row, self.offset_col = op[3]
            elif op[0] == "merge":
                self.cache.insert(op[1], op[2])
                self.cache[op[1] - 1] = op[3]
                self.cursor_col, self.cursor_row, self.display_offset_col, self.display_offset_row, self.offset_col = op[4]
            self.edit_redo_cache.append(op)
            if self.highlight:
                self.highlight_cache.clear()

    def redo(self):
        if len(self.edit_redo_cache) > 0:
            op = self.edit_redo_cache.pop(-1)
            if op[0] == "edit":
                self.cache[op[1]] = op[2]
                self.cursor_col, self.cursor_row, self.display_offset_col, self.display_offset_row, self.offset_col = op[3]
            elif op[0] == "insert":
                self.cache[op[1]] = op[2]
                self.cache.insert(op[1] + 1, op[3])
                self.cursor_col, self.cursor_row, self.display_offset_col, self.display_offset_row, self.offset_col = op[4]
            elif op[0] == "append":
                self.cache[op[1]] = op[2]
                self.cache.insert(op[1] + 1, op[3])
                self.cursor_col, self.cursor_row, self.display_offset_col, self.display_offset_row, self.offset_col = op[4]
            elif op[0] == "insert_row":
                self.cache.insert(op[1], op[2])
                self.cursor_col, self.cursor_row, self.display_offset_col, self.display_offset_row, self.offset_col = op[3]
            elif op[0] == "delete":
                self.cache.pop(op[1])
                self.cursor_col, self.cursor_row, self.display_offset_col, self.display_offset_row, self.offset_col = op[3]
            elif op[0] == "merge":
                self.cache.pop(op[1])
                self.cache[op[1] - 1] = op[3] + op[2]
                self.cursor_col, self.cursor_row, self.display_offset_col, self.display_offset_row, self.offset_col = op[4]
            self.edit_history.append(op)
            if self.highlight:
                self.highlight_cache.clear()
            
    def close(self):
        if hasattr(self.cache, 'close'):
            self.cache.close()
        if hasattr(self.edit_history, 'close'):
            self.edit_history.close()
        if hasattr(self.edit_redo_cache, 'close'):
            self.edit_redo_cache.close()
        self.highlight_cache.clear()

def main(*args, **kwargs):
    #print(kwargs["args"])
    task = args[0]
    name = args[1]
    shell = kwargs["shell"]
    shell_id = kwargs["shell_id"]
    shell_obj_id = kwargs["shell_obj_id"]
    display_id = shell.display_id
    shell.disable_output = True
    width, height = 40, 29
    try:
        if len(kwargs["args"]) > 0:
            file_path = abs_path(kwargs["args"][0])
            ram = True
            if len(kwargs["args"]) > 1:
                ram = int(kwargs["args"][1]) == 1
            s = EditShell(file_path, ram = ram, edit_id = shell_obj_id)
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
            for p in s.load_and_calc_total_lines():
                yield Condition.get().load(sleep = 0, wait_msg = False, send_msgs = [
                    Message.get().load({"frame": s.get_loading_frame(p), "cursor": s.get_cursor_position(1)}, receiver = display_id)
                ])
            yield Condition.get().load(sleep = 0, wait_msg = True, send_msgs = [
                Message.get().load(s.get_frame(), receiver = display_id)
            ])
            msg = task.get_message()
            c = msg.content["msg"]
            msg.release()
            while not s.exit:
                s.input_char(c)
                if s.exit:
                    s.close()
                    gc.collect()
                    break
                yield Condition.get().load(sleep = 0, wait_msg = True, send_msgs = [
                    Message.get().load(s.get_frame(), receiver = display_id)
                ])
                msg = task.get_message()
                c = msg.content["msg"]
                msg.release()
        else:
            yield Condition.get().load(sleep = 0, send_msgs = [
                Message.get().load({"output": "invalid parameters"}, receiver = shell_id)
            ])
        shell.disable_output = False
        shell.current_shell = None
        shell.loading = True
        yield Condition.get().load(sleep = 0, wait_msg = False, send_msgs = [
            Message.get().load({"output": ""}, receiver = shell_id)
        ])
    except Exception as e:
        shell.disable_output = False
        shell.current_shell = None
        shell.loading = True
        buf = StringIO()
        sys.print_exception(e, buf)
        reason = buf.getvalue()
        if reason is None:
            reason = "edit failed"
        yield Condition.get().load(sleep = 0, send_msgs = [
            Message.get().load({"output": str(reason)}, receiver = shell_id)
        ])
