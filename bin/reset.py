import sys
import uos
import time
from math import ceil
from io import StringIO

from lib.scheduler import Condition, Message
from lib.common import exists, path_join, isfile, isdir

coroutine = True


def main(*args, **kwargs):
    task = args[0]
    name = args[1]
    result = "invalid parameters"
    shell = kwargs["shell"]
    shell_id = kwargs["shell_id"]
    display_id = shell.display_id
    try:
        lines = [" "*42 for i in range(50)]
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"clear": True, "output": "\n".join(lines)}, receiver = shell_id)
        ])
    except Exception as e:
        buf = StringIO()
        sys.print_exception(e, buf)
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": buf.getvalue()}, receiver = shell_id)
        ])
