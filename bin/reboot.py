import sys
from machine import Pin, I2C, soft_reset
from io import StringIO

from lib.scheduler import Condition, Message
from lib.common import exists, path_join

coroutine = True


def main(*args, **kwargs):
    task = args[0]
    name = args[1]
    result = "invalid parameters"
    args = kwargs["args"]
    shell_id = kwargs["shell_id"]
    try:
        soft_reset() 
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": "reboot ..."}, receiver = shell_id)
        ])
    except Exception as e:
        buf = StringIO()
        sys.print_exception(e, buf)
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": buf.getvalue()}, receiver = shell_id)
        ])
