import sys
import time
from io import StringIO

from lib.wifi import WIFI
from lib.scheduler import Condition, Message

coroutine = True


def main(*args, **kwargs):
    task = args[0]
    name = args[1]
    result = "invalid parameters"
    shell_id = kwargs["shell_id"]
    try:
        page_size = 18
        n = 2
        WIFI.active(True)
        for ssid in WIFI.scan():
            line = ssid[0].decode("utf-8")
            n += 1
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
                    break
                msg.release()
            else:
                yield task.condition.load(sleep = 0, send_msgs = [
                    Message.get().load({"output_part": line}, receiver = shell_id)
                ])
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": ""}, receiver = shell_id)
        ])
    except Exception as e:
        buf = StringIO()
        sys.print_exception(e, buf)
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": buf.getvalue()}, receiver = shell_id)
        ])
