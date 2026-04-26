import sys
from machine import Pin, I2C
from io import StringIO

from lib.scheduler import Condition, Message
from lib.common import exists, path_join, Time

coroutine = True


def main(*args, **kwargs):
    task = args[0]
    name = args[1]
    result = "invalid parameters"
    args = kwargs["args"]
    shell_id = kwargs["shell_id"]
    try:
        if len(args) > 0:
            if args[0] == "-s":
                if Time.sync():
                    yield task.condition.load(sleep = 0, send_msgs = [
                        Message.get().load({"output": Time.now()}, receiver = shell_id)
                    ])
                else:
                    yield task.condition.load(sleep = 0, send_msgs = [
                        Message.get().load({"output": "sync failed"}, receiver = shell_id)
                    ])
            elif args[0] == "-h":
                yield task.condition.load(sleep = 0, send_msgs = [
                    Message.get().load({"output": Time.now_hardware()}, receiver = shell_id)
                ])
            else:
                yield task.condition.load(sleep = 0, send_msgs = [
                    Message.get().load({"output": Time.now()}, receiver = shell_id)
                ])
        else:
            yield task.condition.load(sleep = 0, send_msgs = [
                Message.get().load({"output": Time.now()}, receiver = shell_id)
            ])
    except Exception as e:
        buf = StringIO()
        sys.print_exception(e, buf)
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": buf.getvalue()}, receiver = shell_id)
        ])
