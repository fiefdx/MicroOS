import sys
import uos
from io import StringIO

from lib.scheduler import Condition, Message
from lib.common import exists, path_join, isfile, isdir, path_split, mkdirs, copy, copyfile, copydir, abs_path

coroutine = True


def main(*args, **kwargs):
    result = "invalid parameters"
    task = args[0]
    name = args[1]
    args = kwargs["args"]
    shell_id = kwargs["shell_id"]
    canceled = False
    try:
        if len(args) == 2:
            s_path = abs_path(args[0])
            t_path = abs_path(args[1])
            for output in copy(s_path, t_path):
                yield task.condition.load(sleep = 0, send_msgs = [
                    Message.get().load({"output_part": output}, receiver = shell_id)
                ])
                msg = task.get_message()
                if msg:
                    c = msg.content["msg"]
                    msg.release()
                    if c == "ES":
                        canceled = True
                        break
            yield task.condition.load(sleep = 0, send_msgs = [
                Message.get().load({"output": "canceled" if canceled else ""}, receiver = shell_id)
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
