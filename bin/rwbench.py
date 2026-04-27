import os
import sys
import time
from io import StringIO
# import micropython

from lib.scheduler import Condition, Message
from lib.common import exists, path_join, isfile, isdir, rmtree, abs_path

coroutine = True


def main(*args, **kwargs):
    task = args[0]
    name = args[1]
    args = kwargs["args"]
    shell_id = kwargs["shell_id"]
    try:
        file_size_bytes =  64 * 1024 # 64 KB
        buffer_size = 512 # 512-byte blocks for writing/reading
        result = "invalid parameters"
        if len(args) > 0:
            target_path = abs_path(args[0])
            if exists(target_path) and isfile(target_path):
                os.remove(target_path)
            start_time = time.ticks_ms()
            try:
                result = ""
                with open(target_path, 'wb') as f:
                    data = bytearray(b'A' * buffer_size)
                    for _ in range(file_size_bytes // buffer_size):
                        f.write(data)
                end_time = time.ticks_ms()
                write_time = time.ticks_diff(end_time, start_time) / 1000
                write_speed = (file_size_bytes / 1024) / write_time if write_time > 0 else 0
                result = f"Write completed in {write_time:.2f} seconds."
                result += f"\nWrite Speed: {write_speed:.2f} KB/s"
            except Exception as e:
                result = f"Write error: {e}"
            start_time = time.ticks_ms()
            try:
                with open(target_path, 'rb') as f:
                    buf = bytearray(buffer_size)
                    while f.readinto(buf) == buffer_size:
                        pass
                end_time = time.ticks_ms()
                read_time = time.ticks_diff(end_time, start_time) / 1000
                read_speed = (file_size_bytes / 1024) / read_time if read_time > 0 else 0
                result += f"\nRead completed in {read_time:.2f} seconds."
                result += f"\nRead Speed: {read_speed:.2f} KB/s"
            except Exception as e:
                result = f"Read error: {e}"
            if exists(target_path) and isfile(target_path):
                os.remove(target_path)
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": result}, receiver = shell_id)
        ])
    except Exception as e:
        buf = StringIO()
        sys.print_exception(e, buf)
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": buf.getvalue()}, receiver = shell_id)
        ])
