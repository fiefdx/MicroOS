import gc
import sys
from machine import Pin, I2C

from lib.scheduler import Condition, Message
from lib.common import Resource

coroutine = True


def main(*args, **kwargs):
    task = args[0]
    name = args[1]
    result = "invalid parameters"
    shell_id = kwargs["shell_id"]
    shell = kwargs["shell"]
    shell.enable_cursor = False
    shell.disable_output = True
    display_id = shell.display_id
    width, height = 40, 28
    try:
        app_exit = False
        # Clear display before showing top
        yield Condition.get().load(sleep = 0, send_msgs = [
            Message.get().load({"clear": True}, receiver = display_id)
        ])
        while not app_exit:
            try:
                frame = []
                gc.collect()
                ram_free = gc.mem_free()
                ram_used = gc.mem_alloc()
                ram_total = ram_free + ram_used
                b = Resource.keyboard.battery_status()
                plugged_in = b["charging"]
                level = b["level"]
                monitor_msg = "CPU%s:%3d%% RAM:%3d%% BATTERY[%s]: %3d%%" % (shell.scheduler.cpu, int(100 - shell.scheduler.idle), int(100 - (ram_free * 100 / ram_total)), "C" if plugged_in else "D", level)
                padding = " " * ((width - len(monitor_msg)) // 2)
                frame.append(padding + monitor_msg)
                frame.append("-" * 40)
                frame.append("% 3s  % 6s %28s" % ("PID", " CPU%", "Name"))
                tasks = []
                tasks.append((0, shell.scheduler.cpu_usage, "system"))
                if shell.scheduler.current is not None:
                    tasks.append((shell.scheduler.current.id, shell.scheduler.current.cpu_usage, shell.scheduler.current.name))
                for i, t in enumerate(shell.scheduler.tasks):
                    tasks.append((t.id, t.cpu_usage, t.name))
                tasks.sort(key = lambda x: x[1], reverse = True)
                for t in tasks:
                    frame.append("%03d % 6.2f%% %28s"  % t)
                for i in range(0, height - len(frame)):
                    frame.append("")
                # Send frame directly to display, bypassing shell cache
                yield Condition.get().load(sleep = 1000, wait_msg = False, send_msgs = [
                    Message.get().load({"frame": frame}, receiver = display_id)
                ])
                yield Condition.get().load(sleep = 1000)
                msg = task.get_message()
                if msg:
                    if msg.content["msg"] == "ES":
                        app_exit = True
                    msg.release()
            except Exception as e:
                print(e)
        shell.disable_output = False
        shell.enable_cursor = True
        shell.loading = True
        yield Condition.get().load(sleep = 0, send_msgs = [
            Message.get().load({"output": ""}, receiver = shell_id)
        ])
    except Exception as e:
        shell.disable_output = False
        shell.enable_cursor = True
        shell.loading = True
        yield Condition.get().load(sleep = 0, send_msgs = [
            Message.get().load({"output": sys.print_exception(e)}, receiver = shell_id)
        ])
