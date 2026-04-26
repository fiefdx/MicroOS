import os
import sys
import gc
from math import ceil
from io import StringIO

from lib.scheduler import Condition, Message
from lib.common import exists, path_join, get_size, path_split, mkdirs, rmtree, copy, Resource, getcwd, abs_path
from lib.display import Colors as C
from bin.edit import EditShell

coroutine = True


class Explorer(object):
    def __init__(self, path = "/", shell = None):
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]
        self.path = path
        self.shell = shell
        self.pwd = None
        self.current_page = 0
        self.page_size = 27
        self.total_pages = 0
        self.cache = []
        self.files = 0
        self.dirs = 0
        self.total = 0
        self.pointer_row = 0
        self.previous_pointer_row = 0
        self.cursor_x = 0
        self.cursor_y = 1
        self.mode = ""
        self.new_name = ""
        self.name_length_limit = 40
        self.cursor_color = 1
        self.warning = ""
        self.status = ""
        self.copied_item = None
        self.quit = 0
        self.editor = None
        self.load()

    def load(self, force = False):
        if exists(self.path):
            fs = os.ilistdir(self.path)
            if self.pwd != self.path or force:
                self.files = 0
                self.dirs = 0
                for f in fs:
                    p = path_join(self.path, f[0])
                    if f[1] == 16384:
                        self.dirs += 1
                    elif f[1] == 32768:
                        self.files += 1
                self.pwd = self.path
                self.total = self.dirs + self.files
                self.total_pages = ceil(self.total / self.page_size)
                if not force:
                    self.current_page = 0
                    self.previous_pointer_row = self.pointer_row
                    self.pointer_row = 0
                self.cache.clear()
            n = 0
            end = False
            self.cache.clear()
            fs = os.ilistdir(self.path)
            for f in fs:
                p = path_join(self.path, f[0])
                if f[1] == 16384:
                    n += 1
                    if n > self.current_page * self.page_size:
                        self.cache.append((f[0], "D", "   0.00B", p))
                    if n == (self.current_page + 1) * self.page_size:
                        end = True
                        break
            if not end:
                fs = os.ilistdir(self.path)
                for f in fs:
                    p = path_join(self.path, f[0])
                    if f[1] == 32768:
                        size = get_size(f[3])
                        n += 1
                        if n > self.current_page * self.page_size:
                            self.cache.append((f[0], "F", size, p))
                        if n == (self.current_page + 1) * self.page_size:
                            break

    def create_file(self):
        if self.mode == "":
            self.mode = "cf"
            self.new_name = ""
            self.cursor_x = 0
            self.shell.enable_cursor = True

    def create_dir(self):
        if self.mode == "":
            self.mode = "cd"
            self.new_name = ""
            self.cursor_x = 0
            self.shell.enable_cursor = True

    def remove(self):
        if len(self.cache) > self.pointer_row:
            if self.mode == "":
                self.mode = "rm"
        else:
            self.warning = "nothing to delete"

    def copy(self):
        self.status = "copied"
        self.copied_item = (self.cache[self.pointer_row], self.path)

    def cut(self):
        self.status = "cutted"
        self.copied_item = (self.cache[self.pointer_row], self.path)

    def paste(self):
        if self.mode == "" and (self.status == "copied" or self.status == "cutted"):
            self.mode = "paste"
            self.new_name = self.copied_item[0][0]
            self.cursor_x = len(self.new_name)
            self.shell.enable_cursor = True

    def rename(self):
        if self.mode == "":
            self.mode = "rename"
            self.new_name = self.cache[self.pointer_row][0]
            self.cursor_x = len(self.new_name)
            self.shell.enable_cursor = True

    def edit(self, file_path):
        if self.mode == "":
            self.mode = "edit"
            self.editor = EditShell(file_path, edit_id=self.shell.shell_id)
            self.shell.enable_cursor = True
            
    def get_editor_init_frame(self):
        frame = self.editor.get_using_ram_frame()
        frame[0] = " " * 13 + "Editor Opening"
        data = {
            "render": (("clean_pointer", "rects"), ("border_lines", "lines"), ("borders", "rects")),
            "frame": frame,
            "cursor": self.editor.get_cursor_position(1),
            "clean_pointer": [[1, self.previous_pointer_row * 11 + 10, 318, 12, C.black], [1, self.pointer_row * 11 + 10, 318, 12, C.black]],
            "border_lines": [[239, 11, 239, 306, C.black], [248, 11, 248, 306, C.black]],
            "borders": [[0, 0, 320, 11, C.white], [0, 0, 320, 319, C.white], [0, 307, 320, 12, C.white]],
        }
        return data
            
    def get_editor_loading_frame(self, p):
        frame = self.editor.get_loading_frame(p)
        frame[0] = " " * 13 + "Editor Opening"
        data = {
            "render": (("clean_pointer", "rects"), ("border_lines", "lines"), ("borders", "rects")),
            "frame": frame,
            "cursor": self.editor.get_cursor_position(1),
            "clean_pointer": [[1, self.previous_pointer_row * 11 + 10, 318, 12, C.black], [1, self.pointer_row * 11 + 10, 318, 12, C.black]],
            "border_lines": [[239, 11, 239, 306, C.black], [248, 11, 248, 306, C.black]],
            "borders": [[0, 0, 320, 11, C.white], [0, 0, 320, 319, C.white], [0, 307, 320, 12, C.white]],
        }
        return data

    def get_frame(self):
        path = self.path
        if len(path) > 40:
            n = len(path) - 40 + 3
            path = self.path[:21 - ceil(n/2)] + "..." + self.path[21 + int(n/2):]
        frame = [path]
        contents = []
        borders = [[0, 0, 320, 11, C.white], [0, 0, 320, 319, C.white], [0, 307, 320, 12, C.white]]
        status = [
            {"s": "%s/%s/%s         " % (self.current_page + 1, self.total_pages, self.total), "c": 20, "x": 3, "y": 310, "C": C.cyan},
            {"s": "% 20s" % self.warning, "c": 20, "x": 151, "y": 310, "C": C.red}
        ]
        render = [("clean_pointer", "rects"), ("border_lines", "lines"), ("borders", "rects"), ("status", "texts"), ("pointer", "rects"), ("contents", "texts")]
        data = {}
        if self.mode == "":
            for f in self.cache:
                name = f[0]
                if len(name) > 29:
                    ext = name.split(".")[-1]
                    if len(ext) > 0:
                        ext = "." + ext
                        name = name[:-len(ext)]
                        name = name[:-(len(name) - (29 - len(ext)) + 3)] + "..." + ext
                else:
                    name += " " * (29 - len(name))
                frame.append("%29s %s %s" % (name, f[1], f[2]))
            while len(frame) < self.page_size + 1:
                frame.append("")
#             print(frame, len(frame))
            border_lines = [[239, 11, 239, 306, C.white], [248, 11, 248, 306, C.white]] #, [2, 1, 2, 125, 0]]
            clean_pointer = [] # [[1, self.previous_pointer_row * 7 + 7, 254, 8, 0], [0, 7, 256, 8, 0]]
            pointer = [[0, self.pointer_row * 11 + 10, 320, 12, C.cyan]]
        elif self.mode == "edit":
            f = self.editor.get_frame()
            frame = None
            if "frame" in f:
                frame = f["frame"]
            if "render" in f:
                for r in f["render"]:
                    render.append(r)
                    data[r[0]] = f[r[0]]
            # border_lines = [[188, 8, 188, 118, 0], [206, 8, 206, 118, 0], [2, 1, 2, 125, 0]]
            border_lines = []
            clean_pointer = [[1, self.previous_pointer_row * 11 + 10, 318, 12, C.black], [1, self.pointer_row * 11 + 10, 318, 12, C.black]]
            borders[0] = [0, 0, 320, 11, C.black]
            pointer = []
            status = []
        elif self.mode == "cf":
            for i in range(self.page_size):
                frame.append("")
            frame[0] = " " * 16 + "New File"
            frame[1] = self.new_name
            border_lines = [[239, 11, 239, 306, C.black], [248, 11, 248, 306, C.black]]
            clean_pointer = [[1, self.previous_pointer_row * 11 + 10, 318, 12, C.black], [1, self.pointer_row * 11 + 10, 318, 12, C.black]]
            pointer = [[0, 10, 320, 12, C.white]]
        elif self.mode == "cd":
            for i in range(self.page_size):
                frame.append("")
            frame[0] = " " * 15 + "New Folder"
            frame[1] = self.new_name
            border_lines = [[239, 11, 239, 306, C.black], [248, 11, 248, 306, C.black]]
            clean_pointer = [[1, self.previous_pointer_row * 11 + 10, 318, 12, C.black], [1, self.pointer_row * 11 + 10, 318, 12, C.black]]
            pointer = [[0, 10, 320, 12, C.white]]
        elif self.mode == "rm":
            for i in range(self.page_size):
                frame.append("")
            target = self.cache[self.pointer_row]
            if target[1] == "F":
                frame[0] = " " * 14 + "Delete File"
            else:
                frame[0] = " " * 13 + "Delete Folder"
            border_lines = [[239, 11, 239, 306, C.black], [248, 11, 248, 306, C.black]]
            clean_pointer = [[1, self.previous_pointer_row * 11 + 10, 318, 12, C.black], [1, self.pointer_row * 11 + 10, 318, 12, C.black]]
            pointer = [[0, 10, 320, 12, C.white]]
            contents.append({"s": "Are you sure you want to delete it?", "c": " ", "x": 3, "y": 24})
            contents.append({"s": "                [y/n]", "c": " ", "x": 3, "y": 35})
            contents.append({"s": target[0], "c": " ", "x": 3, "y": 12})
        elif self.mode == "paste":
            for i in range(self.page_size):
                frame.append("")
            frame[0] = " " * 17 + "Paste"
            frame[1] = self.new_name
            border_lines = [[239, 11, 239, 306, C.black], [248, 11, 248, 306, C.black]]
            clean_pointer = [[1, self.previous_pointer_row * 11 + 10, 318, 12, C.black], [1, self.pointer_row * 11 + 10, 318, 12, C.black]]
            pointer = [[0, 10, 320, 12, C.white]]
#             contents.append({"s": self.new_name, "c": " ", "x": 3, "y": 8})
        elif self.mode == "rename":
            for i in range(self.page_size):
                frame.append("")
            frame[0] = " " * 16 + "Rename"
            frame[1] = self.new_name
            border_lines = [[239, 11, 239, 306, C.black], [248, 11, 248, 306, C.black]]
            clean_pointer = [[1, self.previous_pointer_row * 11 + 10, 318, 12, C.black], [1, self.pointer_row * 11 + 10, 318, 12, C.black]]
            pointer = [[0, 10, 320, 12, C.white]]
#             contents.append({"s": self.new_name, "c": " ", "x": 3, "y": 11})
        data["render"] = render
        if frame is not None:
            data["frame"] = frame
        data["clean_pointer"] = clean_pointer
        data["pointer"] = pointer
        data["borders"] = borders
        data["border_lines"] = border_lines
        data["contents"] = contents
        data["status"] = status
        if self.shell.enable_cursor:
            data["cursor"] = self.get_cursor_position(1)
        return data

    def get_cursor_position(self, c = None):
        if self.mode == "edit":
            return self.editor.get_cursor_position(c)
        else:
            return self.cursor_x, self.cursor_y, self.cursor_color if c is None else c

    def set_cursor_color(self, c):
        if self.mode == "edit":
            self.editor.set_cursor_color(c)
        self.cursor_color = c

    def edit_new_name(self, c):
        if c == "\b":
            delete_before = self.new_name[:self.cursor_x]
            if len(delete_before) > 0:
                self.new_name = self.new_name[:self.cursor_x - 1] + self.new_name[self.cursor_x:]
                self.cursor_x -= 1
        elif c == "LT":
            self.cursor_x -= 1
            if self.cursor_x <= 0:
                self.cursor_x = 0
        elif c == "RT":
            self.cursor_x += 1
            if self.cursor_x >= len(self.new_name):
                self.cursor_x = len(self.new_name)
        elif c == "BB" or c == "ES":
            self.mode = ""
            self.shell.enable_cursor = False
        else:
            if len(c) == 1:
                if len(self.new_name) < self.name_length_limit:
                    self.new_name = self.new_name[:self.cursor_x] + c + self.new_name[self.cursor_x:]
                    self.cursor_x += 1
                    if self.cursor_x >= self.name_length_limit:
                        self.cursor_x = self.name_length_limit

    def input_char(self, c):
        if self.mode == "":
            self.warning = ""
            if c == "UP" or c == "SUP":
                self.previous_pointer_row = self.pointer_row
                self.pointer_row -= 1
                if self.pointer_row <= 0:
                    self.pointer_row = 0
            elif c == "DN" or c == "SDN":
                self.previous_pointer_row = self.pointer_row
                self.pointer_row += 1
                if self.pointer_row >= len(self.cache):
                    self.pointer_row = len(self.cache) - 1
                    if self.pointer_row <= 0:
                        self.pointer_row = 0
            elif c == "LT":
                self.previous_current_page = self.current_page
                self.current_page -= 1
                if self.current_page <= 0:
                    self.current_page = 0
                if self.previous_current_page != self.current_page:
                    self.load()
            elif c == "RT":
                self.previous_current_page = self.current_page
                self.current_page += 1
                if self.current_page >= self.total_pages:
                    self.current_page = self.total_pages - 1
                if self.previous_current_page != self.current_page:
                    self.load()
                    if self.pointer_row >= len(self.cache):
                        self.previous_pointer_row = self.pointer_row
                        self.pointer_row = len(self.cache) - 1
            elif c == "\n" or c == "BA":
                if len(self.cache) > self.pointer_row:
                    f = self.cache[self.pointer_row]
                    if f[1] == "D":
                        self.path = path_join(self.path, f[0])
                        self.load()
                        self.pwd = self.path
                    elif f[1] == "F":
                        ext = f[0].split(".")[-1]
                        if ext.lower() not in ("idx", "mpy", "wav", "mp3"):
                            file_path = path_join(self.path, f[0])
                            self.edit(file_path)
            elif c == "\b" or c == "BB":
                parent, current = path_split(self.path)
                if parent == "":
                    parent = "/"
                if self.path != parent:
                    self.path = parent
                    self.load()
                    self.pwd = self.path
            elif c == "f":
                self.create_file()
            elif c == "d":
                self.create_dir()
            elif c == "r":
                self.remove()
            elif c == "Ctrl-C":
                self.copy()
            elif c == "Ctrl-X":
                self.cut()
            elif c == "Ctrl-V":
                self.paste()
            elif c == "n":
                self.rename()
        elif self.mode == "cf" or self.mode == "cd":
            if c == "\n" or c == "BA":
                new_name = self.new_name.strip()
                if self.mode == "cf" and new_name != "":
                    path = path_join(self.path, new_name)
                    if not exists(path):
                        with open(path, "w") as fp:
                            pass
                        self.mode = ""
                        self.load(force = True)
                        self.shell.enable_cursor = False
                    else:
                        self.warning = "file exists"
                elif self.mode == "cd" and new_name != "":
                    path = path_join(self.path, new_name)
                    if not exists(path):
                        mkdirs(path)
                        self.mode = ""
                        self.load(force = True)
                        self.shell.enable_cursor = False
                    else:
                        self.warning = "folder exists"
            else:
                self.edit_new_name(c)
        elif self.mode == "rm":
            if c == "y":
                if len(self.cache) > self.pointer_row:
                    target = self.cache[self.pointer_row]
                    path = path_join(self.path, target[0])
                    n = 0
                    if exists(path):
                        for p in rmtree(path):
                            n += 1
                        self.warning = "delete %s items" % n
                        self.load(force = True)
                        if len(self.cache) == 0:
                            self.previous_pointer_row = self.pointer_row
                            self.pointer_row = 0
                        elif len(self.cache) < self.pointer_row:
                            self.previous_pointer_row = self.pointer_row
                            self.pointer_row = len(self.cache) - 1
                        elif len(self.cache) == self.pointer_row:
                            self.previous_pointer_row = self.pointer_row
                            self.pointer_row = len(self.cache) - 1
                self.mode = ""
            elif c == "n":
                self.mode = ""
        elif self.mode == "paste":
            if c == "\n" or c == "BA":
                new_name = self.new_name.strip()
                if new_name != "":
                    n = 0
                    source = path_join(self.copied_item[1], self.copied_item[0][0])
                    target = path_join(self.path, new_name)
                    if exists(source):
                        if not exists(target):
                            for i in copy(source, target):
                                n += 1
                            if self.status == "cutted":
                                for i in rmtree(source):
                                    pass
                            self.mode = ""
                            self.load(force = True)
                            self.shell.enable_cursor = False
                            self.warning = "paste %s items" % n
                        else:
                            self.warning = "target exists"
                    else:
                        self.warning = "source not exists"
                else:
                    self.warning = "invalid name"
            else:
                self.edit_new_name(c)
        elif self.mode == "rename":
            if c == "\n" or c == "BA":
                new_name = self.new_name.strip()
                if new_name != "":
                    source = path_join(self.path, self.cache[self.pointer_row][0])
                    target = path_join(self.path, new_name)
                    if exists(source):
                        if not exists(target):
                            os.rename(source, target)
                            self.mode = ""
                            self.load(force = True)
                            self.shell.enable_cursor = False
                        else:
                            self.warning = "name exists"
                    else:
                        self.warning = "source not exists"
                else:
                    self.warning = "invalid name"
            else:
                self.edit_new_name(c)
        elif self.mode == "edit":
            self.editor.input_char(c)
            if self.editor.exit:
                self.mode = ""
                self.shell.enable_cursor = False
                self.editor.close()
                self.editor = None
                gc.collect()


def main(*args, **kwargs):
    task = args[0]
    name = args[1]
    shell = kwargs["shell"]
    shell_id = kwargs["shell_id"]
    display_id = shell.display_id
    cursor_id = shell.cursor_id
    shell.disable_output = True
    shell.enable_cursor = False
#     shell.scheduler.keyboard.scan_rows = 5
    try:
        # yield task.condition.load(sleep = 0, send_msgs = [
        #     Message.get().load({"enabled": False}, receiver = cursor_id)
        # ])
        path = getcwd()
        if len(kwargs["args"]) > 0:
            path = abs_path(kwargs["args"][0])
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]
        if exists(path):
            explorer = Explorer(path, shell)
            shell.current_shell = explorer
            yield task.condition.load(sleep = 0, wait_msg = True, send_msgs = [
                Message.get().load(explorer.get_frame(), receiver = display_id)
            ])
            msg = task.get_message()
            c = msg.content["msg"]
            while explorer.quit < 3:
                if c == "ES" and explorer.mode != "edit":
                    explorer.quit += 1
                    if explorer.quit == 3:
                        break
                else:
                    explorer.quit = 0
                explorer.input_char(c)
                msg.release()
                if explorer.mode == "edit":
                    if explorer.editor.status != "loading":
                        yield task.condition.load(sleep = 0, wait_msg = True, send_msgs = [
                            Message.get().load(explorer.get_frame(), receiver = display_id)
                        ])
                    else: # loading
                        yield task.condition.load(sleep = 0, wait_msg = True, send_msgs = [
                            Message.get().load(explorer.get_editor_init_frame(), receiver = display_id)
                        ])
                        msg = task.get_message()
                        c = msg.content["msg"]
                        if c == "y" or c == "Y" or c == "\n":
                            explorer.editor.set_ram(True)
                        else:
                            explorer.editor.set_ram(False)
                        msg.release()
                        for p in explorer.editor.load_and_calc_total_lines():
                            yield task.condition.load(sleep = 0, wait_msg = False, send_msgs = [
                                Message.get().load(explorer.get_editor_loading_frame(p), receiver = display_id)
                            ])
                        yield task.condition.load(sleep = 0, wait_msg = True, send_msgs = [
                            Message.get().load(explorer.get_frame(), receiver = display_id)
                        ])
                else:
                    yield task.condition.load(sleep = 0, wait_msg = True, send_msgs = [
                        Message.get().load(explorer.get_frame(), receiver = display_id)
                    ])
                msg = task.get_message()
                c = msg.content["msg"]
            msg.release()
        else:
            yield task.condition.load(sleep = 0, send_msgs = [
                Message.get().load({"output": result}, receiver = shell_id)
            ])
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"clear": True}, receiver = display_id)
        ])
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"enabled": True}, receiver = cursor_id)
        ])
        shell.disable_output = False
        shell.enable_cursor = True
        shell.current_shell = None
#         shell.scheduler.keyboard.scan_rows = 5
        shell.loading = True
        yield task.condition.load(sleep = 0, wait_msg = False, send_msgs = [
            Message.get().load({"output": ""}, receiver = shell_id)
        ])
    except Exception as e:
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"clear": True}, receiver = display_id)
        ])
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"enabled": True}, receiver = cursor_id)
        ])
        shell.disable_output = False
        shell.enable_cursor = True
        shell.current_shell = None
#         shell.scheduler.keyboard.scan_rows = 5
        shell.loading = True
        buf = StringIO()
        sys.print_exception(e, buf)
        reason = buf.getvalue()
        if reason is None:
            reason = "render failed"
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": str(reason)}, receiver = shell_id)
        ])
