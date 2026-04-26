import os
import gc
import sys
import time
import random
from math import ceil
from io import StringIO

from lib.shell import Shell
from lib.scheduler import Condition, Message
from lib.common import exists, path_join, isfile, isdir, Resource
from lib.display import Colors as C

coroutine = True


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
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"clear": True}, receiver = display_id)
        ])
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"enabled": False}, receiver = cursor_id)
        ])
        cs = [C.white, C.black, C.red, C.green, C.blue, C.cyan, C.magenta, C.yellow]
        for y in range(2):
            for x in range(4):
                c = cs[x + y * 4]
                Resource.display.fill_rect(x * 80, y * 80, 80, 80, c)
        Resource.display.show()
        yield task.condition.load(sleep = 0, wait_msg = True)           
        msg = task.get_message()
        c = msg.content["msg"]
        msg.release()
        while c != "ES":
            yield task.condition.load(sleep = 0, wait_msg = True)
            msg = task.get_message()
            c = msg.content["msg"]
            msg.release()
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
        buf = StringIO()
        sys.print_exception(e, buf)
        reason = buf.getvalue()
        if reason is None:
            reason = "render failed"
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": str(reason)}, receiver = shell_id)
        ])
        # reason = sys.print_exception(e)
        # if reason is None:
        #     reason = "render failed"
        # yield task.condition.load(sleep = 0, send_msgs = [
        #     Message.get().load({"output": str(reason)}, receiver = shell_id)
        # ])
