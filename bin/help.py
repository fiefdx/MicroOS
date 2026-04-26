from lib.scheduler import Condition, Message

coroutine = True


def main(*args, **kwargs):
    task = args[0]
    name = args[1]
    shell_id = kwargs["shell_id"]
    shell = kwargs["shell"]
    try:
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": shell.help_commands()}, receiver = shell_id)
        ])
    except Exception as e:
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": sys.print_exception(e)}, receiver = shell_id)
        ])