import gc
import sys
import array
from io import StringIO
from time import ticks_ms, ticks_us, ticks_add, ticks_diff, sleep_ms, sleep_us
from micropython import const

_log_buffer = None  # Reusable buffer for error logging


class Message(object):
    pool = []
    free_stack = None  # array.array('H') for compact storage
    free_top = 0       # Stack pointer (number of free items)
    reply_queue = []   # Track messages needing reply (optimization)

    @classmethod
    def init_pool(cls, size = 100):
        cls.pool.clear()
        cls.free_stack = array.array('H', range(size))
        cls.free_top = size
        cls.reply_queue.clear()
        for i in range(size):
            m = Message("", processed = True)
            m._pool_index = i
            cls.pool.append(m)

    @classmethod
    def get(cls):
        if cls.free_top == 0:
            return None
        cls.free_top -= 1
        idx = cls.free_stack[cls.free_top]
        m = cls.pool[idx]
        m.processed = False
        m.replied = False
        return m

    @classmethod
    def need_to_reply(cls):
        # O(1) when no replies needed, O(n) only for actual replies
        for m in cls.reply_queue:
            yield m
        cls.reply_queue.clear()

    @classmethod
    def remain(cls):
        return cls.free_top

    def __init__(self, content, sender = None, sender_name = "", receiver = None, processed = False, drop_size = 0, need_reply = False):
        self.load(content, sender, sender_name, receiver, processed, drop_size, need_reply)

    def load(self, content, sender = None, sender_name = "", receiver = None, processed = False, drop_size = 0, need_reply = False):
        self.content = content
        self.sender = sender
        self.sender_name = sender_name
        self.receiver = receiver
        self.processed = processed
        self.drop_size = drop_size
        self.need_reply = need_reply
        self.replied = True
        return self

    def release(self):
        if self.need_reply:
            self.sender, self.receiver = self.receiver, self.sender
            self.content = self.sender_name
            self.need_reply = False
            self.replied = False
            Message.reply_queue.append(self)  # Re-add to reply queue
        else:
            self.content = ""
            self.sender = None
            self.sender_name = ""
            self.receiver = None
            self.replied = True
            Message.free_stack[Message.free_top] = self._pool_index
            Message.free_top += 1
        self.processed = True


class Condition(object):
    pool = []
    free_stack = None  # array.array('H') for compact storage
    free_top = 0       # Stack pointer (number of free items)

    @classmethod
    def init_pool(cls, size = 100):
        cls.pool.clear()
        cls.free_stack = array.array('H', range(size))
        cls.free_top = size
        for i in range(size):
            c = Condition(processed = True)
            c._pool_index = i
            cls.pool.append(c)

    @classmethod
    def get(cls):
        if cls.free_top == 0:
            return None
        cls.free_top -= 1
        idx = cls.free_stack[cls.free_top]
        c = cls.pool[idx]
        c.resume_at = ticks_us()  # Current time in μs, sleep will be converted in load()
        c.wait_msg = False
        c.send_msgs.clear()
        c.processed = False
        return c

    @classmethod
    def remain(cls):
        return cls.free_top

    def __init__(self, code = 0, sleep = 0, send_msgs = None, wait_msg = False, processed = False):
        self.load(code, sleep, send_msgs, wait_msg, processed)

    def load(self, code = 0, sleep = 0, send_msgs = None, wait_msg = False, processed = False):
        self.code = code
        self.resume_at = ticks_add(ticks_us(), sleep * 1000)  # Convert ms to us
        self.send_msgs = send_msgs if send_msgs is not None else []
        self.wait_msg = wait_msg
        self.processed = processed
        return self

    def release(self):
        self.code = 0
        self.resume_at = 0
        self.send_msgs.clear()
        self.wait_msg = False
        self.processed = True
        # Return to pool using stored index (O(1))
        Condition.free_stack[Condition.free_top] = self._pool_index
        Condition.free_top += 1


class Task(object):
    pool = []
    free_stack = None  # array.array('H') for compact storage
    free_top = 0       # Stack pointer (number of free items)
    id_count = 0

    @classmethod
    def init_pool(cls, size = 100):
        cls.pool.clear()
        cls.free_stack = array.array('H', range(size))
        cls.free_top = size
        for i in range(size):
            t = Task(None, "", processed = True)
            t._pool_index = i
            cls.pool.append(t)

    @classmethod
    def get(cls):
        if cls.free_top == 0:
            return None
        cls.free_top -= 1
        idx = cls.free_stack[cls.free_top]
        t = cls.pool[idx]
        t.processed = False
        return t

    @classmethod
    def remain(cls):
        return cls.free_top

    @classmethod
    def new_id(cls):
        cls.id_count += 1
        return cls.id_count

    def __init__(self, func, name, condition = None, task_id = None, args = None, kwargs = None, need_to_clean = None, reset_sys_path = False, processed = False):
        self.load(func, name, condition, task_id, args, kwargs, need_to_clean, reset_sys_path, processed)

    def load(self, func, name, condition = None, task_id = None, args = None, kwargs = None, need_to_clean = None, reset_sys_path = False, processed = False):
        args = args if args else ()
        kwargs = kwargs if kwargs else {}
        need_to_clean = need_to_clean if need_to_clean else []
        self.id = task_id or Task.new_id()
        self.name = name
        self.msgs = []
        self.msgs_senders = []
        self.func = func(self, name, *args, **kwargs) if func else None
        self.condition = condition if condition else Condition.get()
        self.need_to_clean = need_to_clean
        self.reset_sys_path = reset_sys_path
        self.processed = processed
        self.cpu_time_ms = 0
        self.cpu_usage = 0
        return self

    def set_condition(self, condition):
        if self.condition:
            self.condition.release()
        self.condition = condition

    def put_message(self, message):
        if message.drop_size == 0:
            self.msgs.append(message)
            self.msgs_senders.append(message.sender)
        elif len(self.msgs) < message.drop_size:
            self.msgs.append(message)
            self.msgs_senders.append(message.sender)
        else:
            message.release()

    def get_message(self, sender = None):
        if not self.msgs:
            return None
        if sender is None:
            # O(1) instead of O(n) pop(0)
            msg = self.msgs[0]
            sender_val = self.msgs_senders[0]
            del self.msgs[0]
            del self.msgs_senders[0]
            return msg
            
        try:
            i = self.msgs_senders.index(sender)
            msg = self.msgs[i]
            del self.msgs[i]
            del self.msgs_senders[i]
            return msg
        except ValueError:
            return None

    def ready(self):
        if ticks_diff(ticks_us(), self.condition.resume_at) >= 0:
            if self.condition.wait_msg is True:
                return bool(self.msgs)
            elif self.condition.wait_msg >= 1:
                return self.condition.wait_msg in self.msgs_senders
            else:
                return True
        else:
            return False

    def clean(self):
        for m in self.msgs:
            m.release()
        self.msgs.clear()
        self.msgs_senders.clear()
        self.func = None
        if self.condition:
            self.condition.release()
        self.condition = None
        self.need_to_clean.clear()
        self.reset_sys_path = False
        self.processed = True
        # Return to pool using stored index (O(1))
        Task.free_stack[Task.free_top] = self._pool_index
        Task.free_top += 1


def _sort_key(task):
    return task._sort_key


class Scheduler(object):
    def __init__(self, log_to = None, name = "scheduler", cpu = 0):
        self.log_to = const(log_to)
        self.cpu = const(cpu)
        self.name = const(name)
        self.tasks = []
        self.tasks_ids = {}
        self.task_sort_at = 0
        self.current = None
        self.sleep_ms = 0
        self.load_calc_at = ticks_us()
        self.cpu_time_ms = 0
        self.cpu_usage = 0
        self.idle = 0
        self.idle_sleep_interval = const(100)
        self.task_sleep_interval = const(100)
        self.need_to_sort = True
        self.stop = False

    def task_sort(self, task):
        if task.condition.wait_msg:
            return -1000000 if len(task.msgs) > 0 else 1000000
        return ticks_diff(task.condition.resume_at, self.task_sort_at)

    def add_task(self, task):
        self.tasks.append(task)
        self.tasks_ids[task.id] = task
        self.need_to_sort = True
        return task.id

    def remove_task(self, task):
        if task in self.tasks:
            self.tasks.remove(task)
        del self.tasks_ids[task.id]

    def exists_task(self, task_id):
        return task_id in self.tasks_ids

    def get_task(self, task_id):
        return self.tasks_ids.get(task_id)

    def mem_free(self):
        return gc.mem_free()

    def cpu_idle(self):
        return self.idle

    def set_log_to(self, task_id):
        self.log_to = task_id

    def log(self, head, e):
        global _log_buffer
        try:
            if self.log_to:
                if _log_buffer is None:
                    _log_buffer = StringIO()
                _log_buffer.truncate(0)
                _log_buffer.seek(0)
                sys.print_exception(e, _log_buffer)
                self.tasks_ids[self.log_to].put_message(Message.get().load({"output": head + _log_buffer.getvalue()}, sender = 0, sender_name = self.name))
            else:
                sys.print_exception(e)
        except Exception as e:
            sys.print_exception(e)

    def run(self):
        while not self.stop:
            try:
#                 print("message remain: ", Message.remain())
                load_interval = ticks_diff(ticks_us(), self.load_calc_at)
                if load_interval >= 1000000:
                    load_interval /= 1000
                    self.idle = min(self.sleep_ms * 100 / load_interval, 100)
                    tasks_cpu_time_ms = 0
                    for t in self.tasks:
                        tasks_cpu_time_ms += t.cpu_time_ms
                        t.cpu_usage = t.cpu_time_ms * 100 / load_interval
                        t.cpu_time_ms = 0
                    self.cpu_time_ms = max(load_interval - tasks_cpu_time_ms - self.sleep_ms, 0)
                    self.cpu_usage = self.cpu_time_ms * 100 / load_interval
                    self.cpu_time_ms = 0
                    self.sleep_ms = 0
                    self.load_calc_at = ticks_us()
                if self.tasks:
                    if self.need_to_sort:
                        self.task_sort_at = ticks_us()
                        # Pre-calculate sort keys to reduce overhead during sort
                        for t in self.tasks:
                            if t.condition.wait_msg:
                                t._sort_key = -1000000 if len(t.msgs) > 0 else 1000000
                            else:
                                t._sort_key = ticks_diff(t.condition.resume_at, self.task_sort_at)
                        # Sort in reverse order so pop() gets smallest key (highest priority) in O(1)
                        self.tasks.sort(key=_sort_key, reverse=True)
                        self.need_to_sort = False
                    peek = self.tasks[-1]
                    if peek.ready():
                        self.current = self.tasks.pop()
                        task_start_at = ticks_us()
                        try:
                            self.current.set_condition(next(self.current.func))
                            self.tasks.append(self.current)
                            for msg in self.current.condition.send_msgs:
                                msg.sender = self.current.id
                                msg.sender_name = self.current.name
                                if msg.receiver in self.tasks_ids:
                                    self.tasks_ids[msg.receiver].put_message(msg)
                            self.current.cpu_time_ms = ticks_diff(ticks_us(), task_start_at) / 1000
                            self.current = None
                            self.need_to_sort = True
                        except StopIteration:
                            self.remove_task(self.current)
                            cmd = self.current.name.split(" ")[0]
                            same_cmd_tasks = 0
                            for t in self.tasks:
                                if t.name.startswith(cmd):
                                    same_cmd_tasks += 1
                            if same_cmd_tasks == 0:
                                for m in self.current.need_to_clean:
                                    try:
                                        m_name = m.__name__
                                        if hasattr(m, "main"):
                                            del m.main
                                        del sys.modules[m_name]
                                        gc.collect()
                                    except Exception as e:
                                        h = "task: %s\n" % self.current.name
                                        self.log(h, e)
                                if self.current.reset_sys_path:
                                    try:
                                        sys.path.pop(0)
                                    except Exception as e:
                                        h = "task: %s\n" % self.current.name
                                        self.log(h, e)
                            self.current.clean()
                            self.current = None
                        except TypeError:
                            if self.current:
                                self.current.clean()
                            self.current = None
                        except Exception as e:
                            h = "task: %s\n" % self.current.name
                            self.log(h, e)
                            if self.current:
                                self.current.clean()
                            self.current = None

                        for msg in Message.need_to_reply():
                            msg.processed = False
                            if msg.receiver in self.tasks_ids:
                                self.tasks_ids[msg.receiver].put_message(msg)
                            else:
                                msg.release()
                    else:
                        sleep_us(self.task_sleep_interval)
                        self.sleep_ms += self.task_sleep_interval / 1000
                else:
                    sleep_us(self.idle_sleep_interval)
                    self.sleep_ms += self.idle_sleep_interval / 1000
            except KeyboardInterrupt as e:
                h = "scheduler exit: "
                self.log(h, e)
                break
            except Exception as e:
                h = "scheduler exit: "
                self.log(h, e)
