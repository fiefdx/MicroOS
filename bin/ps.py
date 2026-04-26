from lib.scheduler import Condition, Task, Message

coroutine = False


def main(*args, **kwargs):
    scheduler = kwargs["scheduler"]
    result = ""
    if scheduler.current is not None:
        result += "%03d: %s\n"  % (scheduler.current.id, scheduler.current.name)
    for i, t in enumerate(scheduler.tasks):
        result += "%03d: %s\n"  % (t.id, t.name)
    result += "-" * 40 + "\n"
    result += "Message:%s/%s Task:%s/%s" % (
        Message.remain(), len(Message.pool),
        Task.remain(), len(Task.pool)
    )
    return result
