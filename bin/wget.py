import os
import sys
from io import StringIO
from lib import request as urequests

from lib.scheduler import Condition, Message
from lib.common import exists, path_join, isfile, isdir, Resource, abs_path

coroutine = True

def main(*args, **kwargs):
    task = args[0]
    name = args[1]
    result = "invalid parameters"
    shell_id = kwargs["shell_id"]
    Resource.keyboard.disable = True
    
    args = kwargs["args"]
    
    if len(args) == 0:
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": "Get a file from the net\nUsage:wget <url>"}, receiver = shell_id)
        ])
        return
    
    url = args[0]
    filename = ""
    if url.endswith("/"):
        filename = "index"
    else:
        filename = url.split("/")[-1].split("?")[0]
    try:
        fp = open(abs_path(filename), "wt")
        r = urequests.get(url).raw
        total = 0
        n = 0
        buf = bytearray(6)
        Resource.keyboard.readinto(buf)
        keys = bytes(buf)
        while b'\xb1' not in keys: # ES
            if n % 2048 == 0:
                yield task.condition.load(sleep = 0, send_msgs = [
                    Message.get().load({"output_part": "download: %.2fKB" % (total / 1024)}, receiver = shell_id)
                ])
            read = r.read(512)
            fp.write(read)
            total += len(read)
            if len(read) < 512:
                break
            n += 1
            buf = bytearray(6)
            Resource.keyboard.readinto(buf)
            keys = bytes(buf)
        fp.close()
        if b'\xb1' in keys: # ES
            yield task.condition.load(sleep = 0, send_msgs = [
                Message.get().load({"output": "download partially: %.2fKB" % (total / 1024)}, receiver = shell_id)
            ])
        else:
            yield task.condition.load(sleep = 0, send_msgs = [
                Message.get().load({"output": "download: %.2fKB" % (total / 1024)}, receiver = shell_id)
            ])
        Resource.keyboard.disable = False
    except Exception as e:
        buf = StringIO()
        sys.print_exception(e, buf)
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": buf.getvalue()}, receiver = shell_id)
        ])
        Resource.keyboard.disable = False
