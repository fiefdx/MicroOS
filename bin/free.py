import gc
import sys
# import micropython

from lib.scheduler import Condition, Message

coroutine = True


def main(*args, **kwargs):
    args = kwargs["args"]
    shell_id = kwargs["shell_id"]
    try:
        gc.collect()
        ram_free = gc.mem_free()
        ram_used = gc.mem_alloc()
        ram_total = ram_free + ram_used
        monitor_msg = "R%6.2f%%|F%7.2fk|U%7.2fk" % (100.0 - (ram_free * 100 / ram_total),
                                                          ram_free / 1024,
                                                          ram_used / 1024)
        # print(monitor_msg)
        # micropython.mem_info(True)
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": monitor_msg}, receiver = shell_id)
        ])
    except Exception as e:
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": str(sys.print_exception(e))}, receiver = shell_id)
        ])