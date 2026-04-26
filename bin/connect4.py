import os
import gc
import sys
import time
import random
from math import ceil
from io import StringIO

from lib.shell import Shell
from lib.scheduler import Condition, Message
from lib.common import exists, path_join, isfile, isdir, ticks_ms
from lib.display import Colors as C

coroutine = True


class Disc(object):
    def __init__(self, color, x, y):
        self.x = x
        self.y = y
        self.color = color
        self.frame_n = 0

    def frames(self):
        return (self.y + 1) * 2

    def get_frame(self):
        self.frame_n += 1
        if self.frame_n <= (self.y + 1) * 2:
            return self.color, self.x, (self.frame_n - 1) * self.y / ((self.y + 1) * 2)
        return None, 0, 0


class Game(object):
    def __init__(self, think_games = 100, mode = "2Ps"):
        self.white = 160
        self.black = 161
        self.empty = 162
        self.table = [[self.empty, self.empty, self.empty, self.empty, self.empty, self.empty, self.empty],
                      [self.empty, self.empty, self.empty, self.empty, self.empty, self.empty, self.empty],
                      [self.empty, self.empty, self.empty, self.empty, self.empty, self.empty, self.empty],
                      [self.empty, self.empty, self.empty, self.empty, self.empty, self.empty, self.empty],
                      [self.empty, self.empty, self.empty, self.empty, self.empty, self.empty, self.empty],
                      [self.empty, self.empty, self.empty, self.empty, self.empty, self.empty, self.empty]]
        self.turn = self.black
        self.discs_counter = 0
        self.over = False
        self.win = self.empty
        self.think_games = think_games
        self.think_use_time = 0
        self.mode = mode
        self.disc = Disc(self.black, 0, -1)
        self.think = {self.black: 0, self.white: 0, self.empty: 0}
        self.stats = {self.black: 0, self.white: 0, self.empty: 0}

    def is_full(self):
        return self.discs_counter >= 42

    def available_place_y(self, x):
        for y in range(5, -1, -1):
            if self.table[y][x] == self.empty:
                return y
        return -1

    def available_place_xs(self):
        r = []
        for i, x in enumerate(self.table[0]):
            if x == self.empty:
                r.append(i)
        return r

    def place_disc(self, x, color):
        y = self.available_place_y(x)
        if y != -1:
            self.table[y][x] = color
            self.discs_counter += 1
            return y
        return -1

    def is_same3(self, v1, v2, v3, color):
        return v1 == v2 == v3 == color

    def check_offensive_move23(self, color):
        r = [0, 0, 0, 0, 0, 0, 0]
        for x in range(7):
            y = self.available_place_y(x)
            if y != -1:
                self.table[y][x] = color
                for xx in range(max(0, x - 2), min(x + 1, 5)):
                    if self.is_same3(self.table[y][xx], self.table[y][xx + 1], self.table[y][xx + 2], color):
                        r[x] += 1
                if y <= 3 and self.is_same3(self.table[y][x], self.table[y + 1][x], self.table[y + 2][x], color):
                    r[x] += 1
                for d in range(3):
                    if x - d >= 0 and x - d + 2 <= 6 and y - d >= 0 and y - d + 2 <= 5:
                        if self.is_same3(self.table[y - d][x - d], self.table[y - d + 1][x - d + 1], self.table[y - d + 2][x - d + 2], color):
                            r[x] += 1
                    if x - d >= 0 and x - d + 2 <= 6 and y + d <= 5 and y + d - 2 >= 0:
                        if self.is_same3(self.table[y + d][x - d], self.table[y + d - 1][x - d + 1], self.table[y + d - 2][x - d + 2], color):
                            r[x] += 1
                self.table[y][x] = self.empty
        return r

    def is_line5(self, v1, v2, v3, v4, v5, color):
        return v1 == v5 == self.empty and v2 == v3 == v4 == color

    def check_offensive_win_move23(self, color):
        r = [0, 0, 0, 0, 0, 0, 0]
        for x in range(7):
            y = self.available_place_y(x)
            if y != -1:
                self.table[y][x] = color
                for xx in range(max(0, x - 3), min(x, 3)):
                    if self.is_line5(self.table[y][xx], self.table[y][xx + 1], self.table[y][xx + 2], self.table[y][xx + 3], self.table[y][xx + 4], color) and (y == self.available_place_y(xx) == self.available_place_y(xx + 4)):
                        r[x] += 1
                for d in range(4):
                    if x - d >= 0 and x - d + 4 <= 6 and y - d >= 0 and y - d + 4 <= 5:
                        if self.is_line5(self.table[y - d][x - d], self.table[y - d + 1][x - d + 1], self.table[y - d + 2][x - d + 2], self.table[y - d + 3][x - d + 3], self.table[y - d + 4][x - d + 4], color) and (self.available_place_y(x - d) == y - d and self.available_place_y(x - d + 4) == y - d + 4):
                            r[x] += 1
                    if x - d >= 0 and x - d + 4 <= 6 and y + d <= 5 and y + d - 4 >= 0:
                        if self.is_line5(self.table[y + d][x - d], self.table[y + d - 1][x - d + 1], self.table[y + d - 2][x - d + 2], self.table[y + d - 3][x - d + 3], self.table[y + d - 4][x - d + 4], color)  and (self.available_place_y(x - d) == y + d and self.available_place_y(x - d + 4) == y + d - 4):
                            r[x] += 1
                self.table[y][x] = self.empty
        return r

    def is_any_line4(self, v1, v2, v3, v4, color):
        return ((v1 == v2 == v3 == color and v4 == self.empty) or
                (v1 == v3 == v4 == color and v2 == self.empty) or
                (v2 == v3 == v4 == color and v1 == self.empty) or
                (v1 == v2 == v4 == color and v3 == self.empty))

    def check_offensive_lock_move23(self, color):
        r = [0, 0, 0, 0, 0, 0, 0]
        for x in range(7):
            y = self.available_place_y(x)
            if y != -1:
                self.table[y][x] = color
                for xx in range(max(0, x - 3), min(x + 1, 4)):
                    if self.is_any_line4(self.table[y][xx], self.table[y][xx + 1], self.table[y][xx + 2], self.table[y][xx + 3], color):
                        r[x] += 1
                for d in range(4):
                    if x - d >= 0 and x - d + 3 <= 6 and y - d >= 0 and y - d + 3 <= 5:
                        if self.is_any_line4(self.table[y - d][x - d], self.table[y - d + 1][x - d + 1], self.table[y - d + 2][x - d + 2], self.table[y - d + 3][x - d + 3], color):
                            r[x] += 1
                    if x - d >= 0 and x - d + 3 <= 6 and y + d <= 5 and y + d - 3 >= 0:
                        if self.is_any_line4(self.table[y + d][x - d], self.table[y + d - 1][x - d + 1], self.table[y + d - 2][x - d + 2], self.table[y + d - 3][x - d + 3], color):
                            r[x] += 1
                self.table[y][x] = self.empty
        return r

    def is_same4(self, v1, v2, v3, v4, color):
        return v1 == v2 == v3 == v4 == color

    def check_offensive_move34(self, color):
        r = [0, 0, 0, 0, 0, 0, 0]
        for x in range(7):
            y = self.available_place_y(x)
            if y != -1:
                self.table[y][x] = color
                for xx in range(max(0, x - 3), min(x + 1, 4)):
                    if self.is_same4(self.table[y][xx], self.table[y][xx + 1], self.table[y][xx + 2], self.table[y][xx + 3], color):
                        r[x] += 1
                if y <= 2 and self.is_same4(self.table[y][x], self.table[y + 1][x], self.table[y + 2][x], self.table[y + 3][x], color):
                    r[x] += 1
                for d in range(4):
                    if x - d >= 0 and x - d + 3 <= 6 and y - d >= 0 and y - d + 3 <= 5:
                        if self.is_same4(self.table[y - d][x - d], self.table[y - d + 1][x - d + 1], self.table[y - d + 2][x - d + 2], self.table[y - d + 3][x - d + 3], color):
                            r[x] += 1
                    if x - d >= 0 and x - d + 3 <= 6 and y + d <= 5 and y + d - 3 >= 0:
                        if self.is_same4(self.table[y + d][x - d], self.table[y + d - 1][x - d + 1], self.table[y + d - 2][x - d + 2], self.table[y + d - 3][x - d + 3], color):
                            r[x] += 1
                self.table[y][x] = self.empty
        return r

    def is_line4(self, v1, v2, v3, v4):
        return v1 != self.empty and v1 == v2 == v3 == v4

    def check_status(self, x, y):
        for xx in range(max(0, x - 3), min(x + 1, 4)):
            if self.is_line4(self.table[y][xx], self.table[y][xx + 1], self.table[y][xx + 2], self.table[y][xx + 3]):
                return self.table[y][xx]
        if y <= 2 and self.is_line4(self.table[y][x], self.table[y + 1][x], self.table[y + 2][x], self.table[y + 3][x]):
            return self.table[y][x]
        for d in range(4):
            if x - d >= 0 and x - d + 3 <= 6 and y - d >= 0 and y - d + 3 <= 5:
                if self.is_line4(self.table[y - d][x - d], self.table[y - d + 1][x - d + 1], self.table[y - d + 2][x - d + 2], self.table[y - d + 3][x - d + 3]):
                    return self.table[y - d][x - d]
            if x - d >= 0 and x - d + 3 <= 6 and y + d <= 5 and y + d - 3 >= 0:
                if self.is_line4(self.table[y + d][x - d], self.table[y + d - 1][x - d + 1], self.table[y + d - 2][x - d + 2], self.table[y + d - 3][x - d + 3]):
                    return self.table[y + d][x - d]
        return self.empty

    def drop_disc(self, x):
        y = self.available_place_y(x)
        if y != -1:
            self.disc.color = self.turn
            self.disc.x = x
            self.disc.y = y
            self.disc.frame_n = 0
            return y
        return -1

    def turn_place_disc(self, x):
        y = self.place_disc(x, self.turn)
        if y != -1:
            if self.turn == self.black:
                self.turn = self.white
            else:
                self.turn = self.black
            win = self.check_status(x, y)
            if win != self.empty:
                self.over = True
                self.win = win
                self.stats[self.win] += 1
            if self.is_full():
                if not self.over:
                    self.over = True
                    self.win = self.empty
                    self.stats[self.win] += 1
            return True
        return False

    def check_win_move(self):
        m34 = self.check_offensive_move34(self.turn)
        m34_max = max(m34)
        if m34_max > 0:
            return m34.index(m34_max)
        # for x in range(7):
        #     if m34[x] > 0:
        #         return x
        return -1

    def check_defensive_move(self):
        opponent = self.black if self.turn == self.white else self.white
        # m23 = self.check_offensive_move23(opponent)
        m34 = self.check_offensive_move34(opponent)
        m3 = self.check_offensive_win_move23(opponent)
        # m3l = self.check_offensive_lock_move23(opponent)
        m34_max = max(m34)
        if m34_max > 0:
            idx = [i for i, v in enumerate(m34) if v == m34_max]
            return random.choice(idx)
        m3_max = max(m3)
        if m3_max > 0:
            idx = [i for i, v in enumerate(m3) if v == m3_max]
            return random.choice(idx)
        # for x in range(7):
        #     # if m23[x] > 0 and m34[x] > 0:
        #     #     return x
        #     if m34[x] > 0:
        #         return x
        # for x in range(7):
        #     if m3[x] > 0:
        #         return x
        # for x in range(7):
        #     if m3l[x] > 0:
        #         return x
        return -1

    def turn_random_place_disc(self):
        x = self.check_win_move()
        if x == -1:
            x = self.check_defensive_move()
            if x == -1:
                xs = self.available_place_xs()
                x = random.choice(xs)
        return self.turn_place_disc(x)

    def choose_best_move(self):
        t = ticks_ms()
        if self.discs_counter < 2:
            return 3
        best_x = self.check_win_move()
        if best_x == -1:
            best_x = self.check_defensive_move()
        if best_x == -1:
            xs = self.available_place_xs()
            stats = {}
            g = Game()
            for x in xs:
                stats[x] = {self.black: 0, self.white: 0, self.empty: 0}
                for i in range(self.think_games):
                    g.copy_from(self)
                    g.turn_place_disc(x)
                    while not g.over:
                        g.turn_random_place_disc()
                    stats[x][g.win] += 1
            max_win = stats[xs[0]][self.turn]
            best_x = xs[0]
            for x in xs[1:]:
                if stats[x][self.turn] > max_win: # or (stats[x][self.turn] == max_win and stats[x][self.empty] > stats[best_x][self.empty]):
                    max_win = stats[x][self.turn]
                    best_x = x
            self.think[self.black] = stats[best_x][self.black]
            self.think[self.white] = stats[best_x][self.white]
            self.think[self.empty] = stats[best_x][self.empty]
        self.think_use_time = (ticks_ms() - t) / 1000.0
        return best_x

    def restart(self):
        self.turn = self.black
        self.discs_counter = 0
        self.table = [[self.empty, self.empty, self.empty, self.empty, self.empty, self.empty, self.empty],
                      [self.empty, self.empty, self.empty, self.empty, self.empty, self.empty, self.empty],
                      [self.empty, self.empty, self.empty, self.empty, self.empty, self.empty, self.empty],
                      [self.empty, self.empty, self.empty, self.empty, self.empty, self.empty, self.empty],
                      [self.empty, self.empty, self.empty, self.empty, self.empty, self.empty, self.empty],
                      [self.empty, self.empty, self.empty, self.empty, self.empty, self.empty, self.empty]]
        self.over = False
        self.win = self.empty
        self.think[self.black] = 0
        self.think[self.white] = 0
        self.think[self.empty] = 0
        self.think_use_time = 0
        # self.top_y = 5

    def release(self):
        del self.table

    def copy_from(self, game):
        self.turn = game.turn
        self.discs_counter = game.discs_counter
        self.table = [list(row) for row in game.table]
        self.over = game.over
        self.win = game.win

    def get_frame(self):
        turn = "-turn"
        if self.mode == "black" and self.turn == self.white:
            turn = "-thinking"
        elif self.mode == "white" and self.turn == self.black:
            turn = "-thinking"
        objects = []
        color, x, y = self.disc.get_frame()
        if color is not None:
            objects.append({"x": int(x * 17 + 10), "y": int(y * 17 + 5), "id": color})
        black_info = {"s": "P1(black)" + (turn if self.turn == self.black else "         "), "c": 18, "x": 136, "y": 25}
        white_info = {"s": "P2(white)" + (turn if self.turn == self.white else "         "), "c": 18, "x": 136, "y": 33}
        if self.over:
            if self.win == self.black:
                black_info["s"] = "P1(black)-WIN     "
            elif self.win == self.white:
                white_info["s"] = "P2(white)-WIN     "
            else:
                black_info["s"] = "P1(black)-TIE     "
                white_info["s"] = "P2(white)-TIE     "
        texts = [{"s": "1", "c": 1, "x": 16, "y": 112},
                 {"s": "2", "c": 1, "x": 33, "y": 112},
                 {"s": "3", "c": 1, "x": 50, "y": 112},
                 {"s": "4", "c": 1, "x": 67, "y": 112},
                 {"s": "5", "c": 1, "x": 84, "y": 112},
                 {"s": "6", "c": 1, "x": 101, "y": 112},
                 {"s": "7", "c": 1, "x": 118, "y": 112},
                 {"s": "Status", "c": 6, "x": 172, "y": 10},
                 black_info,
                 white_info,
                 {"s": "black won: %d  " % self.stats[self.black], "c": 16, "x": 136, "y": 41},
                 {"s": "white won: %d  " % self.stats[self.white], "c": 16, "x": 136, "y": 49},
                 {"s": "tie:       %d  " % self.stats[self.empty], "c": 16, "x": 136, "y": 57},
                 {"s": "Think", "c": 6, "x": 175, "y": 75},
                 {"s": "time:  %.3fs   " % self.think_use_time, "c": 16, "x": 136, "y": 90},
                 {"s": "black: %d/%d  " % (self.think[self.black], self.think_games), "c": 16, "x": 136, "y": 98},
                 {"s": "white: %d/%d  " % (self.think[self.white], self.think_games), "c": 16, "x": 136, "y": 106},
                 {"s": "tie:   %d/%d  " % (self.think[self.empty], self.think_games), "c": 16, "x": 136, "y": 114},]
        return {
            "render": (("rects", "rects"), ("lines", "lines"), ("tiles", "tiles"), ("objects", "objects"), ("texts", "texts")),
            "tiles": {
                "data": self.table,
                "width": 7,
                "height": 6,
                "size_w": 17,
                "size_h": 17,
                "offset_x": 10,
                "offset_y": 5,
            },
            "lines": [[9, 106, 128, 106, 1],
                      [10, 21, 127, 21, 1],
                      [10, 38, 127, 38, 1],
                      [10, 55, 127, 55, 1],
                      [10, 72, 127, 72, 1],
                      [10, 89, 127, 89, 1],
                      [26, 5, 26, 105, 1],
                      [43, 5, 43, 105, 1],
                      [60, 5, 60, 105, 1],
                      [77, 5, 77, 105, 1],
                      [94, 5, 94, 105, 1],
                      [111, 5, 111, 105, 1]],
            "rects": [[9, 4, 120, 120, 1],
                      [6, 1, 285, 126, 1],
                      [131, 4, 157, 63, 1],
                      [131, 4, 157, 18, 1],
                      [131, 69, 157, 55, 1],
                      [131, 69, 157, 18, 1],],
            "objects": objects,
            "texts": texts,
        }


def main(*args, **kwargs):
    task = args[0]
    name = args[1]
    shell = kwargs["shell"]
    shell_id = kwargs["shell_id"]
    display_id = shell.display_id
    cursor_id = shell.cursor_id
    shell.disable_output = True
    shell.enable_cursor = False
    shell.scheduler.keyboard.scan_rows = 5
    tiles = [
        {"id": 161, "body": {
            "tile": [
                0b00000000,0b00000000,
                0b00001111,0b11110000,
                0b00010000,0b00001000,
                0b00100000,0b00000100,
                0b01000000,0b00000010,
                0b01000000,0b00000010,
                0b01000000,0b00000010,
                0b01000000,0b00000010,
                0b01000000,0b00000010,
                0b01000000,0b00000010,
                0b01000000,0b00000010,
                0b01000000,0b00000010,
                0b00100000,0b00000100,
                0b00010000,0b00001000,
                0b00001111,0b11110000,
                0b00000000,0b00000000],
            "width": 16, "height": 16
        }},
        {"id": 160, "body": {
            "tile": [
                0b00000000,0b00000000,
                0b00001111,0b11110000,
                0b00011111,0b11111000,
                0b00111111,0b11111100,
                0b01111111,0b11111110,
                0b01111111,0b11111110,
                0b01111111,0b11111110,
                0b01111111,0b11111110,
                0b01111111,0b11111110,
                0b01111111,0b11111110,
                0b01111111,0b11111110,
                0b01111111,0b11111110,
                0b00111111,0b11111100,
                0b00011111,0b11111000,
                0b00001111,0b11110000,
                0b00000000,0b00000000],
            "width": 16, "height": 16
        }},
        {"id": 162, "body": {
            "tile": [
                0b00000000,0b00000000,
                0b00000000,0b00000000,
                0b00000000,0b00000000,
                0b00000000,0b00000000,
                0b00000000,0b00000000,
                0b00000000,0b00000000,
                0b00000000,0b00000000,
                0b00000000,0b00000000,
                0b00000000,0b00000000,
                0b00000000,0b00000000,
                0b00000000,0b00000000,
                0b00000000,0b00000000,
                0b00000000,0b00000000,
                0b00000000,0b00000000,
                0b00000000,0b00000000,
                0b00000000,0b00000000],
            "width": 16, "height": 16
        }},
    ]
    try:
        game_mode = "2Ps"
        think_games = 51
        if len(kwargs["args"]) >= 0:
            if len(kwargs["args"]) > 0:
                if kwargs["args"][0] == "1":
                    game_mode = "black"
                else:
                    game_mode = "white"
            if len(kwargs["args"]) > 1:
                think_games = int(kwargs["args"][1])
            offset_x = 97
            offset_y = 7
            width = 10
            height = 20
            size = 6
            frame_interval = 30
            yield task.condition.load(sleep = 0, send_msgs = [
                Message.get().load({"clear": True}, receiver = display_id)
            ])
            yield task.condition.load(sleep = 0, send_msgs = [
                Message.get().load({"update_tiles": tiles}, receiver = display_id)
            ])
            yield task.condition.load(sleep = 0, send_msgs = [
                Message.get().load({"enabled": False}, receiver = cursor_id)
            ])
            game = Game(think_games, game_mode)
            yield task.condition.load(sleep = frame_interval, wait_msg = False, send_msgs = [
                Message.get().load(game.get_frame(), receiver = display_id)
            ])
            if game_mode == "white":
                x = game.choose_best_move()
                y = game.drop_disc(x)
                if y != -1:
                    for i in range(game.disc.frames()):
                        yield task.condition.load(sleep = frame_interval, wait_msg = False, send_msgs = [
                            Message.get().load(game.get_frame(), receiver = display_id)
                        ])
                    game.turn_place_disc(x)
                    yield task.condition.load(sleep = frame_interval, wait_msg = False, send_msgs = [
                        Message.get().load(game.get_frame(), receiver = display_id)
                    ])
            
            c = None
            msg = task.get_message()
            if msg:
                c = msg.content["msg"]
                msg.release()
            while c != "ES":
                if not game.over:
                    if c in ["1", "2", "3", "4", "5", "6", "7"]:
                        if game_mode == "2Ps" or (game_mode == "black" and game.turn == game.black) or (game_mode == "white" and game.turn == game.white):
                            y = game.drop_disc(int(c) - 1)
                            if y != -1:
                                for i in range(game.disc.frames()):
                                    yield task.condition.load(sleep = frame_interval, wait_msg = False, send_msgs = [
                                        Message.get().load(game.get_frame(), receiver = display_id)
                                    ])
                                game.turn_place_disc(int(c) - 1)
                                yield task.condition.load(sleep = frame_interval, wait_msg = False, send_msgs = [
                                    Message.get().load(game.get_frame(), receiver = display_id)
                                ])
                                if not game.over and (game_mode == "black" or game_mode == "white"):
                                    x = game.choose_best_move()
                                    y = game.drop_disc(x)
                                    if y != -1:
                                        for i in range(game.disc.frames()):
                                            yield task.condition.load(sleep = frame_interval, wait_msg = False, send_msgs = [
                                                Message.get().load(game.get_frame(), receiver = display_id)
                                            ])
                                        game.turn_place_disc(x)
                                        yield task.condition.load(sleep = frame_interval, wait_msg = False, send_msgs = [
                                            Message.get().load(game.get_frame(), receiver = display_id)
                                        ])
                    elif c == "c":
                        x = game.choose_best_move()
                        y = game.drop_disc(x)
                        if y != -1:
                            for i in range(game.disc.frames()):
                                yield task.condition.load(sleep = frame_interval, wait_msg = False, send_msgs = [
                                    Message.get().load(game.get_frame(), receiver = display_id)
                                ])
                            game.turn_place_disc(x)
                            yield task.condition.load(sleep = frame_interval, wait_msg = False, send_msgs = [
                                Message.get().load(game.get_frame(), receiver = display_id)
                            ])
                if c == "r":
                    game.restart()
                    yield task.condition.load(sleep = frame_interval, wait_msg = False, send_msgs = [
                        Message.get().load(game.get_frame(), receiver = display_id)
                    ])
                    if game_mode == "white":
                        x = game.choose_best_move()
                        y = game.drop_disc(x)
                        if y != -1:
                            for i in range(game.disc.frames()):
                                yield task.condition.load(sleep = frame_interval, wait_msg = False, send_msgs = [
                                    Message.get().load(game.get_frame(), receiver = display_id)
                                ])
                            game.turn_place_disc(x)
                            yield task.condition.load(sleep = frame_interval, wait_msg = False, send_msgs = [
                                Message.get().load(game.get_frame(), receiver = display_id)
                            ])
                msg = task.get_message()
                if msg:
                    c = msg.content["msg"]
                    msg.release()
                else:
                    c = None
                yield task.condition.load(sleep = 0)
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
        shell.scheduler.keyboard.scan_rows = 5
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
        shell.scheduler.keyboard.scan_rows = 5
        shell.loading = True
        reason = sys.print_exception(e)
        if reason is None:
            reason = "render failed"
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": str(reason)}, receiver = shell_id)
        ])
