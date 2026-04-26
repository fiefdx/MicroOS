import os
import gc
import sys
import time
import random
from math import ceil, sqrt
from io import StringIO
from time import ticks_ms, ticks_diff

from lib.shell import Shell
from lib.scheduler import Condition, Message
from lib.common import exists, path_join, isfile, isdir, Resource
from lib.display import Colors as C

coroutine = True


class Bullet(object):
    def __init__(self, speed, bullet_id):
        self.id = bullet_id
        self.x = None
        self.y = None
        self.direction = None
        self.speed = speed
        self.frames = 0
        self.fired = False
        
    def fire(self, x, y, direction):
        self.x = x
        self.y = y
        self.direction = direction
        self.fired = True
        
    def update(self, width, height, check_collision):
        self.frames += 1
        if self.fired and self.frames >= self.speed:
            self.frames = 0
            if self.direction == "up":
                self.y -= 1
                if self.y < 0:
                    self.fired = False
            elif self.direction == "down":
                self.y += 1
                if self.y > height - 1:
                    self.fired = False
            elif self.direction == "left":
                self.x -= 1
                if self.x < 0:
                    self.fired = False
            elif self.direction == "right":
                self.x += 1
                if self.x > width - 1:
                    self.fired = False
        check_collision(self)
                
                
class Tank(object):
    def __init__(self, speed, bullets, bullet_speed, tank_id):
        self.id = tank_id
        self.x = None
        self.y = None
        self.direction = None
        self.speed = speed
        self.frames = 0
        self.bullet_speed = bullet_speed
        self.bullets = [Bullet(bullet_speed, self.id) for i in range(bullets)]
        self.live = False
        self.next_direction = None
        self.next_fire = None
        self.next_fire_at = 0
        self.next_live_at = 0
        
    def set_live(self, x, y, direction):
        self.x = x
        self.y = y
        self.direction = direction
        self.live = True

    def bricks(self):
        if self.direction == "up":
            return ((self.x, self.y-1), (self.x, self.y), (self.x-1, self.y), (self.x+1, self.y), (self.x-1, self.y+1), (self.x+1, self.y+1))
        elif self.direction == "down":
            return ((self.x, self.y+1), (self.x, self.y), (self.x-1, self.y), (self.x+1, self.y), (self.x-1, self.y-1), (self.x+1, self.y-1))
        elif self.direction == "left":
            return ((self.x-1, self.y), (self.x, self.y), (self.x, self.y+1), (self.x, self.y-1), (self.x+1, self.y+1), (self.x+1, self.y-1))
        elif self.direction == "right":
            return ((self.x+1, self.y), (self.x, self.y), (self.x, self.y+1), (self.x, self.y-1), (self.x-1, self.y+1), (self.x-1, self.y-1))
        return ()
        
    def fire_ready(self):
        for b in self.bullets:
            if not b.fired:
                return True
        return False

    def no_fired_bullet(self):
        for b in self.bullets:
            if b.fired:
                return False
        return True
    
    def fire(self):
        directions = {
            "up": (0, -1),
            "left": (-1, 0),
            "right": (1, 0),
            "down": (0, 1),
        }
        for b in self.bullets:
            if not b.fired:
                d = directions[self.direction]
                b.fire(self.x + d[0], self.y + d[1], self.direction)
                self.next_fire_at = ticks_ms() + 500
                break
                
    def update_bullets(self, width, height, check_collision):
        for b in self.bullets:
            if b.fired:
                b.update(width, height, check_collision)
        
    def update(self, width, height, runnable, check_collision):
        if self.live:
            self.frames += 1
            if self.frames >= self.speed:
                self.frames = 0
                next_step = "forward"
                if self.fire_ready():
                    next_step = random.choice(["forward", "forward", "forward", "turn", "fire"])
                else:
                    next_step = random.choice(["forward", "forward", "forward", "turn"])
                if next_step == "forward":
                    if self.direction == "up":
                        if self.y > 1 and runnable(self.x, self.y, self.direction):
                            self.y -= 1
                    elif self.direction == "down" and runnable(self.x, self.y, self.direction):
                        if self.y < height - 2:
                            self.y += 1
                    elif self.direction == "left" and runnable(self.x, self.y, self.direction):
                        if self.x > 1:
                            self.x -= 1
                    elif self.direction == "right" and runnable(self.x, self.y, self.direction):
                        if self.x < width - 2:
                            self.x += 1
                elif next_step == "turn":
                    directions = ["up", "left", "right", "down"]
                    directions.remove(self.direction)
                    self.direction = random.choice(directions)
                else:
                    self.fire()
        self.update_bullets(width, height, check_collision)
        
    def update_player(self, keys, width, height, runnable, check_collision):
#         print(keys)
        self.frames += 1
        if self.frames >= self.speed:
            self.frames = 0
            if "UP" in keys:
                if self.direction != "up":
                    self.direction = "up"
                elif runnable(self.x, self.y, "up"):
                    if self.direction == "up":
                        self.y -= 1
            elif "DN" in keys:
                if self.direction != "down":
                    self.direction = "down"
                elif runnable(self.x, self.y, "down"):
                    if self.direction == "down":
                        self.y += 1
            elif "LT" in keys:
                if self.direction != "left":
                    self.direction = "left"
                elif runnable(self.x, self.y, "left"):
                    if self.direction == "left":
                        self.x -= 1
            elif "RT" in keys:
                if self.direction != "right":
                    self.direction = "right"
                elif runnable(self.x, self.y, "right"):
                    if self.direction == "right":
                        self.x += 1
        else:
            if "UP" in keys:
                if self.direction != "up":
                    self.direction = "up"
            elif "DN" in keys:
                if self.direction != "down":
                    self.direction = "down"
            elif "LT" in keys:
                if self.direction != "left":
                    self.direction = "left"
            elif "RT" in keys:
                if self.direction != "right":
                    self.direction = "right"
        if ("BA" in keys or "\b" in keys) and ticks_diff(ticks_ms(), self.next_fire_at) > 0 and self.fire_ready():
            self.fire()


class World(object):
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.frame_p = None
        self.frame_c = self.clear_frame()
        self.tanks = []
        self.player = None
        self.kills = 0
        
    def clear_frame(self):
        data = []
        for h in range(self.height):
            data.append([])
            for w in range(self.width):
                data[h].append(0)
        return data
        
    def have_space(self, x, y):
        return any(self.frame_c[y-1][x-1:x+2]) is False and any(self.frame_c[y][x-1:x+2]) is False and any(self.frame_c[y+1][x-1:x+2]) is False and \
               any(self.frame_p[y-1][x-1:x+2]) is False and any(self.frame_p[y][x-1:x+2]) is False and any(self.frame_p[y+1][x-1:x+2]) is False

    def is_bullet(self, x, y):
        for t in self.tanks:
            for b in t.bullets:
                if b.fired and b.x == x and b.y == y:
                    return True
        for b in self.player.bullets:
            if b.fired and b.x == x and b.y == y:
                return True
        return False

    def runnable(self, x, y, direction):
        directions = {
            "up": ((-1, -2), (0, -2), (1, -2)),
            "left": ((-2, -1), (-2, 0), (-2, 1)),
            "right": ((2, -1), (2, 0), (2, 1)),
            "down": ((-1, 2), (0, 2), (1, 2)),
        }
        return all([((self.height > y + d[1] >= 0 and self.width > x + d[0] >= 0) and \
                     (not self.frame_p[y + d[1]][x + d[0]] and not self.frame_c[y + d[1]][x + d[0]]) or \
                     self.is_bullet(x + d[0], y + d[1])) for d in directions[direction]])
        
    def place_tank(self, tank):
        directions = ["up", "left", "right", "down"]
        direction = random.choice(directions)
        positions = []
        if self.have_space(1, 1):
            positions.append((1, 1))
        if self.have_space(self.width - 2, 1):
            positions.append((self.width - 2, 1))
        if positions:
            x, y = random.choice(positions)
            tank.set_live(x, y, direction)
            return True
        return False

    def place_player(self, tank, x, y):
        tank.set_live(x, y, "up")
        self.player = tank
        self.player.live = True
            
    def draw_tank(self, tank):
        if tank.direction == "up":
            self.frame_c[tank.y-1][tank.x] = tank.id
            self.frame_c[tank.y][tank.x] = tank.id
            self.frame_c[tank.y][tank.x-1] = tank.id
            self.frame_c[tank.y][tank.x+1] = tank.id
            self.frame_c[tank.y+1][tank.x-1] = tank.id
            self.frame_c[tank.y+1][tank.x+1] = tank.id
        elif tank.direction == "down":
            self.frame_c[tank.y+1][tank.x] = tank.id
            self.frame_c[tank.y][tank.x] = tank.id
            self.frame_c[tank.y][tank.x-1] = tank.id
            self.frame_c[tank.y][tank.x+1] = tank.id
            self.frame_c[tank.y-1][tank.x-1] = tank.id
            self.frame_c[tank.y-1][tank.x+1] = tank.id
        elif tank.direction == "left":
            self.frame_c[tank.y][tank.x-1] = tank.id
            self.frame_c[tank.y][tank.x] = tank.id
            self.frame_c[tank.y+1][tank.x] = tank.id
            self.frame_c[tank.y-1][tank.x] = tank.id
            self.frame_c[tank.y+1][tank.x+1] = tank.id
            self.frame_c[tank.y-1][tank.x+1] = tank.id
        elif tank.direction == "right":
            self.frame_c[tank.y][tank.x+1] = tank.id
            self.frame_c[tank.y][tank.x] = tank.id
            self.frame_c[tank.y+1][tank.x] = tank.id
            self.frame_c[tank.y-1][tank.x] = tank.id
            self.frame_c[tank.y+1][tank.x-1] = tank.id
            self.frame_c[tank.y-1][tank.x-1] = tank.id

    def draw_bullets(self, tank):
        for b in tank.bullets:
            if b.fired:
                self.frame_c[b.y][b.x] = tank.id

    def check_collision(self, bullet):
        for t in self.tanks:
            for b in t.bullets:
                if b.fired and b.x == bullet.x and b.y == bullet.y and bullet.id != b.id:
                    b.fired = False
                    bullet.fired = False
                    break
        if bullet.fired:
            for b in self.player.bullets:
                if b.fired and b.x == bullet.x and b.y == bullet.y and bullet.id != b.id:
                    b.fired = False
                    bullet.fired = False
                    break
        if bullet.fired:
            for t in self.tanks:
                if t.live:
                    for b in t.bricks():
                        if bullet.x == b[0] and bullet.y == b[1]:
                            if bullet.id == self.player.id:
                                t.live = False
                                t.next_live_at = ticks_ms() + 1000
                                self.kills += 1
                                for tb in t.bullets:
                                    for bb in t.bricks():
                                        if tb.x == bb[0] and tb.y == bb[1]:
                                            tb.fired = False
                            if bullet.id != t.id:
                                bullet.fired = False
                                break
        if bullet.fired:
            for b in self.player.bricks():
                if bullet.x == b[0] and bullet.y == b[1]:
                    if bullet.id != self.player.id:
                        bullet.fired = False
                        self.player.live = False
                        break
        
    def update(self, keys):
        self.frame_p = self.frame_c
        self.frame_c = self.clear_frame()
        self.player.update_player(keys, self.width, self.height, self.runnable, self.check_collision)
        if self.player.live:
            self.draw_tank(self.player)
        self.player.update_bullets(self.width, self.height, self.check_collision)
        self.draw_bullets(self.player)
        for t in self.tanks:
            t.update(self.width, self.height, self.runnable, self.check_collision)
            if not t.live and ticks_ms() > t.next_live_at and t.no_fired_bullet():
                if self.place_tank(t):
                    self.draw_tank(t)
            elif t.live:
                self.draw_tank(t)
            # t.update_bullets(self.width, self.height, self.check_collision)
            self.draw_bullets(t)
                
    def get_diff_frame(self):
        frame = self.clear_frame()
        for y in range(self.height):
            for x in range(self.width):
                if (self.frame_c[y][x] > 0 and self.frame_p[y][x] == 0) or (self.frame_c[y][x] == 0 and self.frame_p[y][x] > 0):
                    frame[y][x] = "x" if self.frame_c[y][x] else "o"
        return frame
    
    def reset(self):
        self.frame_p = None
        self.frame_c = self.clear_frame()
        for t in self.tanks:
            t.live = False
            for b in t.bullets:
                b.fired = False
        for b in self.player.bullets:
            b.fired = False
        self.player.x = 16
        self.player.y = 19
        self.player.live = True
        self.kills = 0


def main(*args, **kwargs):
    #print(kwargs["args"])
    task = args[0]
    name = args[1]
    shell = kwargs["shell"]
    shell_id = kwargs["shell_id"]
    display_id = shell.display_id
    cursor_id = shell.cursor_id
    shell.disable_output = True
    shell.enable_cursor = False
    Resource.keyboard.disable = True
    width, height = 21, 9
    try:
        width = 39
        height = 38
        size = 8
        frame_interval = 20
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"clear": True}, receiver = display_id)
        ])
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"enabled": False}, receiver = cursor_id)
        ])
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({
                "render": (("borders", "rects"), ("status", "texts")),
                "borders": [[3, 14, 314, 306, 1]],
                "status": [{"s": "kill: %05d" % 0, "c": 12, "x": 229, "y": 2}],
            }, receiver = display_id)
        ])
        w = World(width, height)
        w.tanks.append(Tank(5, 1, 3, 1))
        w.tanks.append(Tank(5, 1, 3, 2))
        w.tanks.append(Tank(5, 1, 3, 3))
        w.tanks.append(Tank(5, 1, 3, 4))
        w.place_player(Tank(1, 3, 2, 100), 16, 19)
        w.update("")
        yield task.condition.load(sleep = frame_interval, wait_msg = False, send_msgs = [
            Message.get().load({
                "render": (("bricks", "bricks"),),
                "bricks": {"offset_x": 4, "offset_y": 15, "data": w.get_diff_frame(), "width": width, "height": height, "size": size}}, receiver = display_id)
        ])
        buf = bytearray(6)
        Resource.keyboard.readinto(buf)
        keys = bytes(buf)
            
        n = 0
        # t = ticks_ms()
        fs = ticks_ms()
        while b"ES" not in keys:
            if b"r" in keys:
                w.reset()
                yield task.condition.load(sleep = 0, send_msgs = [
                    Message.get().load({
                        "clear": True,
                        "render": (("borders", "rects"), ("status", "texts")),
                        "borders": [[3, 14, 314, 306, 1]],
                        "status": [{"s": "kill: %05d" % w.kills, "c": 12, "x": 229, "y": 2}],
                    }, receiver = display_id)
                ])
            w.update(keys)
            # n += 1
            # if n == 100:
            #     n = 0
            #     print("fps:", 100 / ((ticks_ms() - t) / 1000))
            #     t = ticks_ms()
#             k.clear()
            already_used_time = ticks_ms() - fs
            sleep_time = 0
            if frame_interval > already_used_time:
                sleep_time = frame_interval - already_used_time
            yield task.condition.load(sleep = sleep_time, wait_msg = False, send_msgs = [
                Message.get().load({
                    "render": (("bricks", "bricks"), ("status", "texts")),
                    "bricks": {"offset_x": 4, "offset_y": 15, "data": w.get_diff_frame(), "width": width, "height": height, "size": size},
                    "status": [{"s": "kill: %05d" % w.kills, "c": 12, "x": 229, "y": 2}],
                }, receiver = display_id)
            ])
            fs = ticks_ms()
            buf = bytearray(6)
            Resource.keyboard.readinto(buf)
            keys = bytes(buf)
#             keys = k.scan_keys()
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"clear": True}, receiver = display_id)
        ])
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"enabled": True}, receiver = cursor_id)
        ])
        shell.disable_output = False
        shell.enable_cursor = True
        shell.current_shell = None
        Resource.keyboard.disable = False
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
        Resource.keyboard.disable = False
        shell.loading = True
        buf = StringIO()
        sys.print_exception(e, buf)
        reason = buf.getvalue()
        if reason is None:
            reason = "edit failed"
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": str(reason)}, receiver = shell_id)
        ])
