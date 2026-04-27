import gc
import sys
from machine import Pin, I2C
from io import StringIO

from lib.scheduler import Condition, Message
from lib.common import Resource

coroutine = True


def main(*args, **kwargs):
    task = args[0]
    name = args[1]
    result = "invalid parameters"
    args = kwargs["args"]
    shell_id = kwargs["shell_id"]
    shell = kwargs["shell"]
    try:
        gc.collect()
        ram_free = gc.mem_free()
        ram_used = gc.mem_alloc()
        ram_total = ram_free + ram_used
        b = Resource.keyboard.battery_status()
        plugged_in = b["charging"]
        level = b["level"]
        monitor_msg = "CPU%s:%3d%% RAM:%3d%% BATTERY[%s]: %3d%%" % (shell.scheduler.cpu, int(100 - shell.scheduler.idle), int(100 - (ram_free * 100 / ram_total)), "C" if plugged_in else "D", level)
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": monitor_msg}, receiver = shell_id)
        ])
    except Exception as e:
        buf = StringIO()
        sys.print_exception(e, buf)
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": buf.getvalue()}, receiver = shell_id)
        ])
