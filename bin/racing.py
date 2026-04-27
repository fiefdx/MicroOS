import os
import gc
import sys
import time
import random
from math import ceil
from io import StringIO
from time import ticks_ms, ticks_diff

from lib.shell import Shell
from lib.scheduler import Condition, Message
from lib.common import exists, path_join, isfile, isdir, Resource
from lib.display import Colors as C

coroutine = True

# --- Constants ---
ROAD_WIDTH = 11          # road in grid columns
ROAD_LEFT = 4            # left edge of road
LANE_COUNT = 3
# Lanes: each lane is 3 cells wide, centers at 5, 8, 11
LANE_CENTERS = [ROAD_LEFT + 1, ROAD_LEFT + 1 + 3, ROAD_LEFT + 1 + 6]  # 5, 8, 11
SCREEN_W = 20            # grid width for bricks
SCREEN_H = 20            # grid height for bricks
FRAME_INTERVAL = 15      # ms per frame
INIT_SPEED = 0.25        # rows scrolled per tick
MAX_SPEED = 1.5          # max speed

# Car sprites: 3 wide x 4 tall (OXO/XXX/OXO/XXX pattern)
PLAYER_CELLS = [
    (1, 0),              # row 0: OXO
    (0, 1), (1, 1), (2, 1),  # row 1: XXX
    (1, 2),              # row 2: OXO
    (0, 3), (1, 3), (2, 3),  # row 3: XXX
]

ENEMY_CELLS = [
    (1, 0),              # row 0: OXO
    (0, 1), (1, 1), (2, 1),  # row 1: XXX
    (1, 2),              # row 2: OXO
    (0, 3), (1, 3), (2, 3),  # row 3: XXX
]


class Car(object):
    def __init__(self, x, y, car_type="player"):
        self.x = x
        self.y = y
        self.type = car_type
        self.cells = PLAYER_CELLS if car_type == "player" else ENEMY_CELLS
        self.alive = True

    def abs_cells(self):
        """Return set of absolute (col, row) positions."""
        return set((self.x + dx, self.y + dy) for dx, dy in self.cells)

    def collides(self, other):
        return bool(self.abs_cells() & other.abs_cells())


def _clear_frame(w, h):
    return [["o"] * w for _ in range(h)]


class Game(object):
    def __init__(self):
        self.speed = INIT_SPEED
        self.score = 0
        self.distance = 0
        self.game_over = False
        self.best_score = 0
        self.started = False
        self.player = None
        self.enemies = []
        self.road_scroll = 0
        self.spawn_timer = 0
        self.spawn_interval = 60
        # Frame buffers for diff rendering
        self.frame_c = None
        self.frame_p = None

    def reset(self):
        self.speed = INIT_SPEED
        self.score = 0
        self.distance = 0
        self.game_over = False
        self.best_score = self.best_score
        self.started = False
        self.player = Car(LANE_CENTERS[1], SCREEN_H - 5, "player")
        self.enemies = []
        self.road_scroll = 0
        self.spawn_timer = 0
        self.spawn_interval = 60
        self.frame_c = None
        self.frame_p = None

    def spawn_enemy(self):
        lane = random.randint(0, LANE_COUNT - 1)
        x = LANE_CENTERS[lane]
        y = -3
        e = Car(x, y, "enemy")
        for existing in self.enemies:
            if e.collides(existing):
                return
        self.enemies.append(e)

    def _draw_road(self, frame):
        """Draw road onto a frame buffer.
        Road = "o" (black), cars = "x" (white).
        """
        for y in range(SCREEN_H):
            for x in range(ROAD_LEFT, ROAD_LEFT + ROAD_WIDTH):
                frame[y][x] = "o"
            # Road edge stripes (white)
            yy = (y + self.road_scroll) % 4
            if yy < 2:
                frame[y][ROAD_LEFT - 1] = "x"
                frame[y][ROAD_LEFT + ROAD_WIDTH] = "x"
            # Lane dashes (white)
            yy2 = (y + self.road_scroll) % 8
            if yy2 < 3:
                for lane_edge in [LANE_CENTERS[0] + 1, LANE_CENTERS[1] + 1]:
                    if 0 <= lane_edge < SCREEN_W:
                        frame[y][lane_edge] = "x"

    def _draw_player(self, frame):
        if self.player and self.player.alive:
            for dx, dy in self.player.cells:
                cx = self.player.x + dx
                cy = self.player.y + dy
                if 0 <= cy < SCREEN_H and 0 <= cx < SCREEN_W:
                    frame[cy][cx] = "x"

    def _draw_enemies(self, frame):
        for e in self.enemies:
            if e.alive:
                for dx, dy in e.cells:
                    cx = e.x + dx
                    cy = e.y + dy
                    if 0 <= cy < SCREEN_H and 0 <= cx < SCREEN_W:
                        frame[cy][cx] = "x"

    def update(self, keys):
        if self.game_over:
            return

        if not self.started:
            if "UP" in keys:
                self.started = True
            return

        # Player lane changes
        if "LT" in keys:
            idx = LANE_CENTERS.index(self.player.x) if self.player.x in LANE_CENTERS else 1
            if idx > 0:
                self.player.x = LANE_CENTERS[idx - 1]
        if "RT" in keys:
            idx = LANE_CENTERS.index(self.player.x) if self.player.x in LANE_CENTERS else 1
            if idx < LANE_COUNT - 1:
                self.player.x = LANE_CENTERS[idx + 1]

        # Scroll road markers
        self.road_scroll = (self.road_scroll + int(self.speed)) % 8

        # Score & distance
        self.distance += int(self.speed)
        self.score = self.distance // 10

        # Gradual speed increase
        if self.speed < MAX_SPEED:
            self.speed += 0.005

        # Spawn enemies
        self.spawn_timer += 1
        if self.spawn_timer >= self.spawn_interval:
            self.spawn_timer = 0
            self.spawn_enemy()
            if random.random() < 0.25:
                self.spawn_enemy()

        # Move enemies
        for e in self.enemies[:]:
            e.y += int(self.speed)
            if e.y > SCREEN_H + 5:
                self.enemies.remove(e)
                self.score += 3

        # Collision check
        player_cells = self.player.abs_cells()
        for e in self.enemies[:]:
            if player_cells & e.abs_cells():
                self.game_over = True
                if self.score > self.best_score:
                    self.best_score = self.score
                break

    def build_frame(self):
        """Build current full frame and compute diff against previous frame.
        Returns (diff, texts).
        diff[h][w] = "x" if changed to white, "o" if changed to black, "" if unchanged.
        """
        # Build current full frame
        frame_c = _clear_frame(SCREEN_W, SCREEN_H)
        self._draw_road(frame_c)
        self._draw_player(frame_c)
        self._draw_enemies(frame_c)

        # Compute diff against previous frame
        diff = [[""] * SCREEN_W for _ in range(SCREEN_H)]

        if self.frame_p is None:
            # First frame: everything changed
            for y in range(SCREEN_H):
                for x in range(SCREEN_W):
                    diff[y][x] = "x" if frame_c[y][x] == "x" else "o"
        else:
            for y in range(SCREEN_H):
                for x in range(SCREEN_W):
                    if self.frame_p[y][x] != frame_c[y][x]:
                        diff[y][x] = "x" if frame_c[y][x] == "x" else "o"

        self.frame_p = self.frame_c
        self.frame_c = frame_c

        # --- HUD text ---
        texts = []
        texts.append({"s": "score: %05d" % self.score, "c": 12, "x": 160, "y": 7, "C": C.yellow})
        texts.append({"s": "spd: %d" % int(self.speed), "c": 10, "x": 160, "y": 17, "C": C.cyan})
        texts.append({"s": "best: %05d" % self.best_score, "c": 10, "x": 160, "y": 27, "C": C.green})

        if not self.started:
            texts.append({"s": "Press UP to start", "c": 16, "x": 160, "y": 55, "C": C.white})
            texts.append({"s": "LT/RT: change lane", "c": 16, "x": 160, "y": 65, "C": C.white})
            texts.append({"s": "ES: exit", "c": 16, "x": 160, "y": 75, "C": C.white})
        elif self.game_over:
            texts.append({"s": "GAME OVER!", "c": 14, "x": 160, "y": 50, "C": C.red})
            texts.append({"s": "score: %d" % self.score, "c": 12, "x": 160, "y": 62, "C": C.yellow})
            texts.append({"s": "Press R to restart", "c": 16, "x": 160, "y": 72, "C": C.white})

        return diff, texts


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
        size = 8
        frame_interval = FRAME_INTERVAL

        # --- Init display ---
        yield task.condition.load(sleep=0, send_msgs=[
            Message.get().load({"clear": True}, receiver=display_id)
        ])
        yield task.condition.load(sleep=0, send_msgs=[
            Message.get().load({"enabled": False}, receiver=cursor_id)
        ])
        yield task.condition.load(sleep=frame_interval, wait_msg=False, send_msgs=[
            Message.get().load({
                "render": (("borders", "rects"),),
                "borders": [[3, 14, 314, 306, C.yellow]],
            }, receiver=display_id)
        ])

        # --- Create game ---
        g = Game()
        g.reset()
        diff, texts = g.build_frame()

        yield task.condition.load(sleep=frame_interval, wait_msg=False, send_msgs=[
            Message.get().load({
                "render": (("bricks", "bricks"), ("status", "texts")),
                "bricks": {
                    "offset_x": 4, "offset_y": 15,
                    "data": diff,
                    "width": SCREEN_W, "height": SCREEN_H,
                    "size": size,
                },
                "status": texts,
            }, receiver=display_id)
        ])

        # --- Input loop ---
        c = None
        keys = []
        msg = task.get_message()
        if msg:
            c = msg.content["msg"]
            keys = msg.content.get("keys", [])
            msg.release()

        while c != "ES":
            # Restart on game over
            if c == "r" and g.game_over:
                g.reset()
                yield task.condition.load(sleep=0, send_msgs=[
                    Message.get().load({
                        "clear": True,
                        "render": (("borders", "rects"),),
                        "borders": [[3, 14, 314, 306, C.yellow]],
                    }, receiver=display_id)
                ])

            g.update(keys)
            keys.clear()
            diff, texts = g.build_frame()

            yield task.condition.load(sleep=frame_interval, wait_msg=False, send_msgs=[
                Message.get().load({
                    "render": (("bricks", "bricks"), ("status", "texts")),
                    "bricks": {
                        "offset_x": 4, "offset_y": 15,
                        "data": diff,
                        "width": SCREEN_W, "height": SCREEN_H,
                        "size": size,
                    },
                    "status": texts,
                }, receiver=display_id)
            ])

            msg = task.get_message()
            if msg:
                c = msg.content["msg"]
                if "keys" in msg.content:
                    keys = msg.content["keys"]
                msg.release()
            else:
                c = None

        # --- Cleanup ---
        yield task.condition.load(sleep=0, send_msgs=[
            Message.get().load({"clear": True}, receiver=display_id)
        ])
        yield task.condition.load(sleep=0, send_msgs=[
            Message.get().load({"enabled": True}, receiver=cursor_id)
        ])
        shell.disable_output = False
        shell.enable_cursor = True
        shell.current_shell = None
        shell.loading = True
        yield task.condition.load(sleep=0, wait_msg=False, send_msgs=[
            Message.get().load({"output": ""}, receiver=shell_id)
        ])

    except Exception as e:
        yield task.condition.load(sleep=0, send_msgs=[
            Message.get().load({"clear": True}, receiver=display_id)
        ])
        yield task.condition.load(sleep=0, send_msgs=[
            Message.get().load({"enabled": True}, receiver=cursor_id)
        ])
        shell.disable_output = False
        shell.enable_cursor = True
        shell.current_shell = None
        shell.loading = True
        buf = StringIO()
        sys.print_exception(e, buf)
        reason = buf.getvalue()
        if reason is None:
            reason = "render failed"
        yield task.condition.load(sleep=0, send_msgs=[
            Message.get().load({"output": str(reason)}, receiver=shell_id)
        ])
