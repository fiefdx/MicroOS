import os
import gc
import sys
import time
import random
from math import ceil
from io import StringIO

from lib.shell import Shell
from lib.scheduler import Condition, Message
from lib.common import exists, path_join, isfile, isdir
from lib.display import Colors as C

coroutine = True


B = {
    0: [[
        "OOOO",
        "OOOO",
        "XXXX",
        "OOOO",
    ], ["OXOO",
        "OXOO",
        "OXOO",
        "OXOO",
    ], ["OOOO",
        "OOOO",
        "XXXX",
        "OOOO",
    ], ["OXOO",
        "OXOO",
        "OXOO",
        "OXOO",
    ]],
    1: [[
        "OXO",
        "XXX",
        "OOO",
    ], ["OXO",
        "OXX",
        "OXO",
    ], ["OOO",
        "XXX",
        "OXO",
    ], ["OXO",
        "XXO",
        "OXO",
    ]],
    2: [[
        "XOO",
        "XXX",
        "OOO",
    ], ["OXX",
        "OXO",
        "OXO",
    ], ["OOO",
        "XXX",
        "OOX",
    ], ["OXO",
        "OXO",
        "XXO",
    ]],
    3: [[
        "OOO",
        "XXX",
        "XOO",
    ], ["XXO",
        "OXO",
        "OXO",
    ], ["OOX",
        "XXX",
        "OOO",
    ], ["OXO",
        "OXO",
        "OXX",
    ]],
    4: [[
        "OOO",
        "OXX",
        "XXO",
    ], ["XOO",
        "XXO",
        "OXO",
    ], ["OOO",
        "OXX",
        "XXO",
    ], ["XOO",
        "XXO",
        "OXO",
    ]],
    5: [[
        "OOO",
        "XXO",
        "OXX",
    ], ["OXO",
        "XXO",
        "XOO",
    ], ["OOO",
        "XXO",
        "OXX",
    ], ["OXO",
        "XXO",
        "XOO",
    ]],
    6: [[
        "XX",
        "XX",
    ], ["XX",
        "XX",
    ], ["XX",
        "XX",
    ], ["XX",
        "XX",
    ]],
}


class Brick(object):
    def __init__(self, x, y, t = 0, d = 0):
        self.type = t
        self.direction = d
        self.brick = B[self.type][self.direction]
        self.x = x
        self.y = self.get_init_offset_y()
        self.frames = 0
        self.status = "falling" # falling, finish
        
    def get_init_offset_y(self):
        result = 0
        brick_size = len(self.brick[0])
        for y in range(brick_size - 1, -1, -1):
            if self.brick[y].count("X") > 0:
                return -y
        return result
        
    def rotate(self, frame):
        if self.status == "falling":
            brick_size = len(self.brick)
            if self.direction == 0:
                self.direction = 1
            elif self.direction == 1:
                self.direction = 2
            elif self.direction == 2:
                self.direction = 3
            elif self.direction == 3:
                self.direction = 0
            rotate_brick = B[self.type][self.direction]
            fx = 0
            lfx = 0
            for iy, line in enumerate(rotate_brick):
                y = self.y + iy
                for ix, c in enumerate(line):
                    x = self.x + ix + lfx
                    if brick_size == 4:
                        x -= 2
                    else:
                        x -= 1
                    if c == "X":
                        if x <= 9:
                            if x >= 0:
                                if y >= 0 and y <= 19:
                                    if frame[y][x]:
                                        lfx += 1
                            else:
                                lfx += 1
                        break
            fx += lfx
            rfx = 0
            for iy, line in enumerate(rotate_brick):
                y = self.y + iy
                for ix in range(brick_size - 1, -1, -1):
                #for ix, c in enumerate(line):
                    c = line[ix]
                    x = self.x + ix + fx
                    if brick_size == 4:
                        x -= 2
                    else:
                        x -= 1
                    if c == "X":
                        if x >= 0:
                            if x <= 9:
                                if y >= 0 and y <= 19:
                                    if frame[y][x]:
                                        rfx -= 1
                                        fx += rfx
                            else:
                                rfx -= (x - 9)
                                fx += rfx
                        break
            if (abs(rfx) > 0 and abs(lfx) > 0):
                pass
            else:
                if rfx == 0 and lfx == 0:
                    fx = 0
                elif abs(rfx) > 0:
                    fx = rfx
                elif abs(lfx) > 0:
                    fx = lfx
                fy = 0
                bfy = 0
                for iy in range(brick_size - 1, -1, -1):
                    line = rotate_brick[iy]
                    for ix, c in enumerate(line):
                        y = self.y + iy + fy
                        c = line[ix]
                        x = self.x + ix + fx
                        if brick_size == 4:
                            x -= 2
                        else:
                            x -= 1
                        if c == "X":
                            iy_below = iy + 1
                            if iy_below < brick_size:
                                c_below = rotate_brick[iy_below][ix]
                                if c_below == "O":
                                    if y <= 19:
                                        if y >= 0:
                                            if frame[y][x]: # error for I
                                                bfy -= 1
                                                fy += bfy
                                    else:
                                        bfy -= 1
                                        fy += bfy
                            else:
                                if y <= 19:
                                    if y >= 0:
                                        if frame[y][x]:
                                            bfy -= 1
                                            fy += bfy
                                else:
                                    bfy -= 1
                                    fy += bfy
                tfy = 0
                for iy, line in enumerate(rotate_brick):
                    for ix, c in enumerate(line):
                        y = self.y + iy + fy
                        c = line[ix]
                        x = self.x + ix + fx
                        if brick_size == 4:
                            x -= 2
                        else:
                            x -= 1
                        if c == "X":
                            iy_above = iy - 1
                            if iy_above >= 0:
                                c_above = rotate_brick[iy_above][ix]
                                if c_above == "O":
                                    if y <= 19:
                                        if y >= 0:
                                            if frame[y][x]:
                                                tfy += 1
                                                fy += tfy
                #print(lfx, rfx, tfy, bfy, fx, fy)
                if (abs(tfy) > 0 and abs(bfy) > 0):
                    pass
                elif tfy == 0 and bfy == 0:
                    self.brick = rotate_brick
                    self.x += fx
                elif abs(bfy) > 0:
                    self.brick = rotate_brick
                    self.x += fx
                    self.y += bfy
                elif abs(tfy) > 0:
                    self.brick = rotate_brick
                    self.x += fx
                    self.y += tfy
        
    def check_bottom(self, frame):
        if self.status == "falling":
            brick_size = len(self.brick)
            for iy, line in enumerate(self.brick):
                y = self.y + iy
                for ix, c in enumerate(line):
                    x = self.x + ix
                    if brick_size == 4:
                        x -= 2
                    else:
                        x -= 1
                    if c == "X":
                        y_below = iy + 1
                        if y_below < brick_size:
                            c_below = self.brick[y_below][ix]
                            if c_below == "O":
                                if y + 1 >= 0 and y + 1 < 20:
                                    f_below = frame[y + 1][x] # error for I
                                    if f_below:
                                        self.status = "finish"
                                        break
                                elif y + 1 >= 20:
                                    self.status = "finish"
                                    break
                        else:
                            if y + 1 >= 0 and y + 1 < 20:
                                f_below = frame[y + 1][x]
                                if f_below:
                                    self.status = "finish"
                                    break
                            elif y + 1 >= 20:
                                self.status = "finish"
                                break
                if self.status == "finish":
                    break
                
    def put_down(self, frame):
        self.check_bottom(frame)
        while self.status == "falling":
            self.y += 1
            self.check_bottom(frame)                
                
    def check_x(self, frame, dx):
        if self.status == "falling":
            brick_size = len(self.brick)
            for iy, line in enumerate(self.brick):
                y = self.y + iy
                for ix, c in enumerate(line):
                    x = self.x + ix
                    if brick_size == 4:
                        x -= 2
                    else:
                        x -= 1
                    if c == "X":
                        if dx < 0:
                            lx = x + dx
                            if lx >= 0:
                                if y >= 0 and y <= 19:
                                    if frame[y][lx]:
                                        return False
                            else:
                                return False
                        elif dx > 0:
                            rx = x + dx
                            if rx <= 9:
                                if y >= 0 and y <= 19:
                                    if frame[y][rx]:
                                        return False
                            else:
                                return False
        return True
        
    def update(self, dx, dy, speed, frame):
        self.frames += 1
        if self.frames >= speed and dy == 0:
            self.frames = 0
            self.check_bottom(frame)
            if self.status == "falling":
                self.y += 1
        if self.status == "falling":
            if dy != 0:
                self.frames = 0
                self.check_bottom(frame)
                if self.status == "falling":
                    self.y += dy
            if dx != 0:
                if self.check_x(frame, dx):
                    self.x += dx


class Game(object):
    def __init__(self, width, height, level_step = 20, level_max = 11):
        self.score = 0
        self.level = 0
        self.level_max = level_max
        self.level_step = level_step
        self.level_speeds = [30, 25, 20, 15, 10, 8, 6, 5, 4, 3, 2, 1]
        self.speed = self.level_speeds[self.level]
        self.width = width
        self.height = height
        self.frame_p = None
        self.frame_c = self.clear_frame(self.width, self.height)
        self.data = self.clear_frame(self.width, self.height)
        self.brick = None
        self.next_brick = None
        self.pause = False
        self.game_over = False
        self.next_frame_p = self.clear_frame(4, 4)
        self.next_frame_c = self.clear_frame(4, 4)
        self.frames = 0
        self.remove_lines = []
        
    def clear_frame(self, width, height):
        data = []
        for h in range(height):
            data.append([])
            for w in range(width):
                data[h].append(False)
        return data
        
    def place_brick(self):
        if self.brick is not None:
            if self.brick.status == "finish":
                self.brick = self.next_brick
                self.next_brick = None
        if self.next_brick is None:            
            self.next_brick = Brick(5, -4, t = random.choice([0, 1, 2, 3, 4, 5, 6]), d = random.choice([0, 1, 2, 3]))
            self.next_frame_p = self.next_frame_c
            self.next_frame_c = self.clear_frame(4, 4)
            dx, dy = 0, 0
            if len(self.next_brick.brick[0]) <= 3:
                dx, dy = 1, 1
            for y, line in enumerate(self.next_brick.brick):
                for x, c in enumerate(line):
                    if c == "X":
                        self.next_frame_c[y + dy][x + dx] = True
        if self.brick is None:
            self.brick = self.next_brick
            self.next_brick = Brick(5, -4, t = random.choice([0, 1, 2, 3, 4, 5, 6]), d = random.choice([0, 1, 2, 3]))
            self.next_frame_p = self.next_frame_c
            self.next_frame_c = self.clear_frame(4, 4)
            dx, dy = 0, 0
            if len(self.next_brick.brick[0]) <= 3:
                dx, dy = 1, 1
            for y, line in enumerate(self.next_brick.brick):
                for x, c in enumerate(line):
                    if c == "X":
                        self.next_frame_c[y + dy][x + dx] = True
            
    def update_data(self):
        if self.brick is not None and self.brick.status == "finish":
            if len(self.brick.brick[0]) == 4:
                for dy, line in enumerate(self.brick.brick):
                    y = self.brick.y + dy
                    for dx, c in enumerate(line):
                        x = self.brick.x - 2 + dx
                        if y >= 0 and y < len(self.data):
                            if c == "X":
                                self.data[y][x] = True
            elif len(self.brick.brick[0]) == 3:
                for dy, line in enumerate(self.brick.brick):
                    y = self.brick.y + dy
                    for dx, c in enumerate(line):
                        x = self.brick.x - 1 + dx
                        if y >= 0 and y < len(self.data):
                            if c == "X":
                                self.data[y][x] = True
            elif len(self.brick.brick[0]) == 2:
                for dy, line in enumerate(self.brick.brick):
                    y = self.brick.y + dy
                    for dx, c in enumerate(line):
                        x = self.brick.x - 1 + dx
                        if y >= 0 and y < len(self.data):
                            if c == "X":
                                self.data[y][x] = True
        data = self.clear_frame(self.width, self.height)
        ii = 19
        if self.frames == 0:
            self.remove_lines = []
        for i in range(19, -1, -1):
            line = self.data[i]
            if line.count(True) == 10:
                if self.frames == 0:
                    self.remove_lines.append(i)
        if len(self.remove_lines) > 0:
            if self.frames == 0:
                self.frames = 1
            else:
                self.frames += 1
            if self.frames >= 4 and self.frames < 12:
                for i in range(19, -1, -1):
                    line = self.data[i]
                    if i not in self.remove_lines:
                        data[i] = line
            elif self.frames >= 12:
                ii = 19
                for i in range(19, -1, -1):
                    line = self.data[i]
                    if i not in self.remove_lines:
                        data[ii] = line
                        ii -= 1
                    else:
                        self.score += 1
                self.frames = 0
                self.remove_lines = []
            else:
                data = self.data
        else:
            data = self.data
            
        self.level = (self.score // self.level_step) % (self.level_max + 1)
        self.speed = self.level_speeds[self.level]
        #print("speed:", self.speed)
        self.data = data
        if self.data[0].count(True) > 0:
            self.game_over = True
            
    def draw_brick(self):
        if self.brick is not None and self.brick.status == "falling":
            if len(self.brick.brick[0]) == 4:
                for dy, line in enumerate(self.brick.brick):
                    y = self.brick.y + dy
                    for dx, c in enumerate(line):
                        x = self.brick.x - 2 + dx
                        if y >= 0 and y < len(self.frame_c):
                            if c == "X":
                                self.frame_c[y][x] = True
            elif len(self.brick.brick[0]) == 3:
                for dy, line in enumerate(self.brick.brick):
                    y = self.brick.y + dy
                    for dx, c in enumerate(line):
                        x = self.brick.x - 1 + dx
                        if y >= 0 and y < len(self.frame_c):
                            if c == "X":
                                self.frame_c[y][x] = True
            elif len(self.brick.brick[0]) == 2:
                for dy, line in enumerate(self.brick.brick):
                    y = self.brick.y + dy
                    for dx, c in enumerate(line):
                        x = self.brick.x - 1 + dx
                        if y >= 0 and y < len(self.frame_c):
                            if c == "X":
                                self.frame_c[y][x] = True

    def draw_data(self):
        for y, line in enumerate(self.data):
            for x, c in enumerate(line):
                self.frame_c[y][x] = self.data[y][x]

    def update(self, keys):
        dx = 0
        dy = 0
        if "LT" in keys:
            dx = -1
        elif "RT" in keys:
            dx = 1
        elif "DN" in keys:
            dy = 1
        if "\b" in keys:
            self.brick.rotate(self.data)
        if "p" in keys:
            self.pause = True if not self.pause else False
        if "UP" in keys:
            self.brick.put_down(self.data)
        if not self.pause and not self.game_over:
            self.frame_p = self.frame_c
            self.frame_c = self.clear_frame(self.width, self.height)
            self.brick.update(dx, dy, self.speed, self.data)
            self.update_data()
            self.draw_data()
            self.draw_brick()
            self.place_brick()

    def get_diff_frame(self):
        frame = self.clear_frame(self.width, self.height)
        for y in range(self.height):
            for x in range(self.width):
                if self.frame_c[y][x] != self.frame_p[y][x]:
                    frame[y][x] = "x" if self.frame_c[y][x] else "o"
        return frame
    
    def get_diff_next_brick(self, current = False):
        frame = self.clear_frame(4, 4)
        for y in range(4):
            for x in range(4):
                if current:
                    frame[y][x] = "x" if self.next_frame_c[y][x] else "o"
                else:
                    if self.next_frame_c[y][x] != self.next_frame_p[y][x]:
                        frame[y][x] = "x" if self.next_frame_c[y][x] else "o"
        return frame


def main(*args, **kwargs):
    task = args[0]
    name = args[1]
    shell = kwargs["shell"]
    shell_id = kwargs["shell_id"]
    display_id = shell.display_id
    cursor_id = shell.cursor_id
    shell.disable_output = True
    shell.enable_cursor = False

    try:
        if len(kwargs["args"]) == 0:
            offset_x = 85
            offset_y = 19
            width = 10
            height = 20
            size = 15
            frame_interval = 30
            yield task.condition.load(sleep = 0, send_msgs = [
                Message.get().load({"clear": True}, receiver = display_id)
            ])
            yield task.condition.load(sleep = 0, send_msgs = [
                Message.get().load({"enabled": False}, receiver = cursor_id)
            ])
            g = Game(width, height)
            g.place_brick()
            g.update("")
            yield task.condition.load(sleep = 0, send_msgs = [
                Message.get().load({"clear": True}, receiver = display_id)
            ])

            yield task.condition.load(sleep = frame_interval, wait_msg = False, send_msgs = [
                Message.get().load({
                    "render": (("rects", "rects"), ), # , ("background", "tiles"), ("area_clear", "tiles"), ("text_clear", "tiles")),
                    "rects": [
                        [248, 62, 62, 62, C.yellow],
#                         [0, 0, 320, 320, C.white],
                        [offset_x - 1, offset_y - 1, 152, 302, C.yellow],
                ]}, receiver = display_id)
            ])
            yield task.condition.load(sleep = frame_interval, wait_msg = False, send_msgs = [
                Message.get().load({
                    "render": (("bricks", "bricks"),),
                    "bricks": {
                        "data": g.get_diff_next_brick(current = True),
                        "width": 4,
                        "height": 4,
                        "size": size,
                        "offset_x": 249,
                        "offset_y": 63,
                    }
                }, receiver = display_id)
            ])
            yield task.condition.load(sleep = frame_interval, wait_msg = False, send_msgs = [
                Message.get().load({
                    "render": (("bricks", "bricks"), ("texts", "texts")),
                    "bricks": {
                        "data": g.get_diff_frame(),
                        "width": width,
                        "height": height,
                        "size": size,
                        "offset_x": offset_x,
                        "offset_y": offset_y,
                    },
                    "texts": [{
                        "s": "score: %05d" % g.score,
                        "c": 13,
                        "x": 70,
                        "y": 7,
                        "C": C.cyan,
                    }, {
                        "s": "level: %02d" % (g.level + 1),
                        "c": 12,
                        "x": 181,
                        "y": 7,
                        "C": C.cyan,
                    }, {
                        "s": "pause" if g.pause else "          ",
                        "c": 5,
                        "x": 259,
                        "y": 45,
                        "C": C.white,
                    }],
                }, receiver = display_id)
            ])
            c = None
            keys = []
            msg = task.get_message()
            if msg:
                c = msg.content["msg"]
                keys = msg.content["keys"]
                msg.release()
            score = g.score
            level = g.level
            pause = g.pause
            brick = g.next_brick
            while c != "ES":
                g.update(keys)
                keys.clear()
                texts = []
                if score != g.score:
                    texts.append({
                        "s": "score: %05d" % g.score,
                        "c": 13,
                        "x": 70,
                        "y": 7,
                        "C": C.cyan,
                    })
                    score = g.score
                if level != g.level:
                    texts.append({
                        "s": "level: %02d" % (g.level + 1),
                        "c": 12,
                        "x": 181,
                        "y": 7,
                        "C": C.cyan,
                    })
                    level = g.level
                if pause != g.pause:
                    texts.append({
                        "s": "pause" if g.pause else 5,
                        "c": 5,
                        "x": 259,
                        "y": 45,
                        "C": C.white,
                    })
                    pause = g.pause
                if g.game_over:
                    texts.append({
                        "s": "game over!",
                        "c": 10,
                        "x": 120,
                        "y": 45,
                        "C": C.red,
                    })
                if brick.type != g.next_brick.type or brick.direction != g.next_brick.direction:
                    yield task.condition.load(sleep = frame_interval, wait_msg = False, send_msgs = [
                        Message.get().load({
                            "render": (("bricks", "bricks"),),
                            "bricks": {
                                "data": g.get_diff_next_brick(current = True),
                                "width": 4,
                                "height": 4,
                                "size": size,
                                "offset_x": 249,
                                "offset_y": 63,
                            }
                        }, receiver = display_id)
                    ])
                    brick = g.next_brick
                yield task.condition.load(sleep = frame_interval, wait_msg = False, send_msgs = [
                    Message.get().load({
                        "render": (("bricks", "bricks"), ("texts", "texts")),
                        "bricks": {
                            "data": g.get_diff_frame(),
                            "width": width,
                            "height": height,
                            "size": size,
                            "offset_x": offset_x,
                            "offset_y": offset_y,
                        },
                        "texts": texts
                    }, receiver = display_id)
                ])
                msg = task.get_message()
                if msg:
                    c = msg.content["msg"]
                    keys.clear()
                    if "keys" in msg.content:
                        keys = msg.content["keys"]
                    msg.release()
                else:
                    c = None
        else:
            yield task.condition.load(sleep = 0, send_msgs = [
                Message.get().load({"output": "invalid parameters"}, receiver = shell_id)
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
#         shell.scheduler.keyboard.game_mode = False
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
#         shell.scheduler.keyboard.game_mode = False
        shell.loading = True
        reason = sys.print_exception(e)
        if reason is None:
            reason = "render failed"
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": str(reason)}, receiver = shell_id)
        ])
