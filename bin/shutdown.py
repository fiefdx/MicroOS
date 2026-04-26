import sys
from machine import Pin, I2C
from io import StringIO

from lib.scheduler import Condition, Message
from lib.common import exists, path_join

coroutine = True


def main(*args, **kwargs):
    result = "invalid parameters"
    args = kwargs["args"]
    shell_id = kwargs["shell_id"]
    try:
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": "not implemented yet!"}, receiver = shell_id)
        ])
    except Exception as e:
        buf = StringIO()
        sys.print_exception(e, buf)
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": buf.getvalue()}, receiver = shell_id)
        ])
