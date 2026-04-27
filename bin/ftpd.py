import sys

from lib import uftpd

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
        if len(args) > 0:
            if args[0] == "start":
                r = uftpd.start(splash = False)
                yield task.condition.load(sleep = 0, send_msgs = [
                    Message.get().load({"output": r}, receiver = shell_id)
                ])
            elif args[0] == "stop":
                r = uftpd.stop()
                yield task.condition.load(sleep = 0, send_msgs = [
                    Message.get().load({"output": r}, receiver = shell_id)
                ])
            elif args[0] == "restart":
                r = uftpd.restart(splash = False)
                yield task.condition.load(sleep = 0, send_msgs = [
                    Message.get().load({"output": r}, receiver = shell_id)
                ])
            elif args[0] == "status":
                yield task.condition.load(sleep = 0, send_msgs = [
                    Message.get().load({"output": "ftpd: %s" % uftpd.status}, receiver = shell_id)
                ])
            else:
                yield task.condition.load(sleep = 0, send_msgs = [
                    Message.get().load({"output": "Usage: ftpd start|stop|restart"}, receiver = shell_id)
                ])
        else:
            yield task.condition.load(sleep = 0, send_msgs = [
                Message.get().load({"output": "Usage: ftpd start|stop|restart"}, receiver = shell_id)
            ])
    except Exception as e:
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": str(sys.print_exception(e))}, receiver = shell_id)
        ])
