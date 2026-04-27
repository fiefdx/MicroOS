import os
import sys
# import micropython

from lib.scheduler import Condition, Message
from lib.common import exists

coroutine = True


def main(*args, **kwargs):
    task = args[0]
    name = args[1]
    args = kwargs["args"]
    shell_id = kwargs["shell_id"]
    try:
        disk = "Disk"
        result = "{disk: <8}{total: >10}{free: >10}{used: >10}".format(
            disk = "Disk", total = "Total", free = "Free", used = "Used")
        stat = os.statvfs("/")
        size = stat[1] * stat[2]
        free = stat[0] * stat[3]
        used = size - free
        result += "\n{disk: <8}{total: >10}{free: >10}{used: >10}".format(
            disk = "/", total = "%7.2fK" % (size / 1024), free = "%7.2fK" % (free / 1024), used = "%7.2fK" % (used / 1024))
        if exists("/sd"):
            stat = os.statvfs("/sd")
            size = stat[1] * stat[2]
            free = stat[0] * stat[3]
            used = size - free
            result += "\n{disk: <8}{total: >10}{free: >10}{used: >10}".format(
                disk = "/sd", total = "%8.2fM" % (size / 1024 / 1024), free = "%8.2fM" % (free / 1024 / 1024), used = "%8.2fM" % (used / 1024 / 1024))
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": result}, receiver = shell_id)
        ])
    except Exception as e:
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": str(sys.print_exception(e))}, receiver = shell_id)
        ])
