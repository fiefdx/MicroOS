import sys
import uos
from io import StringIO

from lib.scheduler import Condition, Message
from lib.zipfile import ZipFile
from lib.common import exists, path_join, abs_path, path_split

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
                dir_path, _ = path_split(path)
                z = ZipFile(path)
                for zipinfo in z.namelist():
                    target_path = z._extract_member(zipinfo, dir_path, None)
                    yield task.condition.load(sleep = 0, send_msgs = [
                        Message.get().load({"output_part": target_path}, receiver = shell_id)
                    ])
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
        reason = buf.getvalue()
        print(reason)
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": sys.print_exception(e)}, receiver = shell_id)
        ])
