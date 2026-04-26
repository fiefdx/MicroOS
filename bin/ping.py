import os
import sys
from io import StringIO

from lib.uping import ping
from lib.scheduler import Condition, Message
from lib.common import exists, path_join, get_size

coroutine = True


def main(*args, **kwargs):
    task = args[0]
    name = args[1]
    result = "invalid parameters"
    shell_id = kwargs["shell_id"]
    target = None
    if len(kwargs["args"]) > 0:
        host = kwargs["args"][0]
    try:
        if host:
            for line in ping(host):
                yield task.condition.load(sleep = 0, send_msgs = [
                    Message.get().load({"output_part": line}, receiver = shell_id)
                ])
            yield task.condition.load(sleep = 0, send_msgs = [
                Message.get().load({"output": ""}, receiver = shell_id)
            ])
        else:
            yield task.condition.load(sleep = 0, send_msgs = [
                Message.get().load({"output": result}, receiver = shell_id)
            ])
    except Exception as e:
        buf = StringIO()
        sys.print_exception(e, buf)
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": buf.getvalue()}, receiver = shell_id)
        ])

