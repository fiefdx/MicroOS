import sys
import time
from io import StringIO

from lib.scheduler import Task, Condition, Message
from lib.common import exists, path_join, Time

coroutine = True


def main(*args, **kwargs):
    result = "invalid parameters"
    args = kwargs["args"]
    shell_id = kwargs["shell_id"]
    try:
        now = Time.now()
        uptime_seconds = time.time() - Time.start_at
        uptime_days = uptime_seconds // 86400
        uptime_seconds_remaining = uptime_seconds % 86400
        uptime_hms = time.gmtime(uptime_seconds_remaining)
        
        result = "{} up {} days, {:0>2}:{:0>2}:{:0>2}".format(
            now[11:19], 
            uptime_days, uptime_hms[3], uptime_hms[4], uptime_hms[5]
        )
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": result}, receiver = shell_id)
        ])
    except Exception as e:
        buf = StringIO()
        sys.print_exception(e, buf)
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": buf.getvalue()}, receiver = shell_id)
        ])
