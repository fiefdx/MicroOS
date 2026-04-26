import gc
import sys
from io import StringIO

from lib.scheduler import Condition, Message

coroutine = True


def main(*args, **kwargs):
    task = args[0]
    name = args[1]
    shell_id = kwargs["shell_id"]
    shell = kwargs["shell"]
    try:
        shell.clear_cache()
        gc.collect()
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": ""}, receiver = shell_id)
        ])
    except Exception as e:
        buf = StringIO()
        sys.print_exception(e, buf)
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": buf.getvalue()}, receiver = shell_id)
        ])
