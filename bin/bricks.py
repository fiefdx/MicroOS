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

coroutine = True


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
    width, height = 21, 9
    try:
        if len(kwargs["args"]) > 2:
            width = int(kwargs["args"][0])
            height = int(kwargs["args"][1])
            size = int(kwargs["args"][2])
            yield task.condition.load(sleep = 0, send_msgs = [
                Message.get().load({"clear": True}, receiver = display_id)
            ])
            yield task.condition.load(sleep = 0, send_msgs = [
                Message.get().load({"enabled": False}, receiver = cursor_id)
            ])
            data = []
            for h in range(height):
                data.append([])
                for w in range(width):
                    if h % 2 == 0:
                        data[h].append("x" if w % 2 == 0 else "o")
                    else:
                        data[h].append("o" if w % 2 == 0 else "x")
            yield task.condition.load(sleep = 0, wait_msg = True, send_msgs = [
                Message.get().load({
                    "render": (("bricks", "bricks"),),
                    "bricks": {"offset_x": 0, "offset_y": 0, "data": data, "width": width, "height": height, "size": size}}, receiver = display_id)
            ])
            msg = task.get_message()
            c = msg.content["msg"]
            msg.release()
            while c != "ES":
                for h in range(height):
                    for w in range(width):
                        data[h][w] = "x" if data[h][w] == "o" else "o"
                yield task.condition.load(sleep = 0, wait_msg = True, send_msgs = [
                    Message.get().load({
                        "render": (("bricks", "bricks"),),
                        "bricks": {"offset_x": 0, "offset_y": 0, "data": data, "width": width, "height": height, "size": size}}, receiver = display_id)
                ])
                msg = task.get_message()
                c = msg.content["msg"]
                msg.release()
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
        reason = sys.print_exception(e)
        if reason is None:
            reason = "render failed"
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": str(reason)}, receiver = shell_id)
        ])
