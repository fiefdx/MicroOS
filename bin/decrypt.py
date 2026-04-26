import sys
import uos
from io import StringIO

from lib.scheduler import Condition, Message
from lib.common import exists, path_join, isfile, isdir, path_split, mkdirs, copy, copyfile, copydir, abs_path
from lib.tea import CryptFile

coroutine = True


def main(*args, **kwargs):
    result = "invalid parameters"
    task = args[0]
    name = args[1]
    args = kwargs["args"]
    shell_id = kwargs["shell_id"]
    try:
        if len(args) == 2:
            password = args[0]
            file_path = abs_path(args[1])
            if exists(file_path) and isfile(file_path):
                f = CryptFile(file_path)
                success = f.open_source_file()
                if success is True:
                    for m in f.decrypt(key = password):
                        yield task.condition.load(sleep = 0, send_msgs = [
                            Message.get().load({"output_part": m}, receiver = shell_id)
                        ])
                    yield task.condition.load(sleep = 0, send_msgs = [
                        Message.get().load({"output": ""}, receiver = shell_id)
                    ])
                else:
                    yield task.condition.load(sleep = 0, send_msgs = [
                        Message.get().load({"output": success}, receiver = shell_id)
                    ])
            else:
                yield task.condition.load(sleep = 0, send_msgs = [
                    Message.get().load({"output": "%s not exists!" % file_path}, receiver = shell_id)
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
