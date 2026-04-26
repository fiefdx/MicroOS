import os
import io
import gc
import sys
import time
import micropython

from lib.scheduler import Condition, Message
from lib.common import exists, path_join, abs_path

coroutine = True


def main(*args, **kwargs):
    task = args[0]
    name = args[1]
    result = "invalid parameters"
    args = kwargs["args"]
    shell_id = kwargs["shell_id"]
    try:
        if len(args) > 0:
            path = abs_path(args[0])
            with open(path, "w") as f:
                f.write(f"@@@ {time.ticks_ms()}\n")
                buf = io.StringIO()
                os.dupterm(buf)
                gc.collect()
                micropython.mem_info(1)
                os.dupterm(None)
                buf.seek(0)
                line = buf.readline()
                while line:
                    f.write(line)
                    line = buf.readline()
                f.write("@@@\n")
            result = path
            yield task.condition.load(sleep = 0, send_msgs = [
                Message.get().load({"output": result}, receiver = shell_id)
            ])
        else:
            yield task.condition.load(sleep = 0, send_msgs = [
                Message.get().load({"output": result}, receiver = shell_id)
            ])
    except Exception as e:
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": sys.print_exception(e)}, receiver = shell_id)
        ])
