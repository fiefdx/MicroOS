import sys
import uos
from io import StringIO

from lib.scheduler import Condition, Message
from lib import utarfile
from lib.common import exists, path_join, abs_path, path_split, mkdirs

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
                t = utarfile.TarFile(path)
                for i in t:
                    if i.type == utarfile.DIRTYPE:
                        target_path = path_join(dir_path, i.name)
                        yield task.condition.load(sleep = 0, send_msgs = [
                            Message.get().load({"output_part": target_path}, receiver = shell_id)
                        ])
                        mkdirs(target_path)
                    else:
                        f = t.extractfile(i)
                        target_path = path_join(dir_path, i.name)
                        yield task.condition.load(sleep = 0, send_msgs = [
                            Message.get().load({"output_part": target_path}, receiver = shell_id)
                        ])
                        w = open(target_path, "wb")
                        buf = f.read(512)
                        while buf:
                            w.write(buf)
                            buf = f.read(512)
                        w.close()
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
