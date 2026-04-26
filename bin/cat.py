import sys
import uos
from io import StringIO

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
            if exists(path):
                n = 0
                page_size = 18
                with open(path, "r") as fp:
                    line = fp.readline()
                    while line:
                        n += 1
                        line = line.replace("\r", "")
                        line = line.replace("\n", "")
                        if n == page_size:
                            n = 0
                            yield task.condition.load(sleep = 0, wait_msg = True, send_msgs = [
                                Message.get().load({"output_part": line}, receiver = shell_id)
                            ])
                            msg = task.get_message()
                            while msg.content["msg"] != "ES":
                                if msg.content["msg"] == "\n":
                                    break
                                msg.release()
                                yield task.condition.load(sleep = 0, wait_msg = True)
                                msg = task.get_message()
                            if msg.content["msg"] == "ES":
                                msg.release()
                                break
                            msg.release()
                        else:
                            yield task.condition.load(sleep = 0, send_msgs = [
                                Message.get().load({"output_part": line}, receiver = shell_id)
                            ])
                        line = fp.readline()
                    yield task.condition.load(sleep = 0, send_msgs = [
                        Message.get().load({"output": ""}, receiver = shell_id)
                    ])
            else:
                yield task.condition.load(sleep = 0, send_msgs = [
                    Message.get().load({"output": result}, receiver = shell_id)
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
