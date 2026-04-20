import os
import sys
import gc
import time
import uos
import framebuf
import socket
machine = None
microcontroller = None
try:
    import machine
except:
    try:
        import microcontroller
    except:
        print("no machine & microcontroller module support")
thread = None
try:
    import _thread as thread
except:
    print("no multi-threading module support")
from machine import Pin, SPI, PWM
from micropython import const

import sdcard
import font8
# import font7
from display import ILI9488
from scheduler import Scheduler, Condition, Task, Message
from common import ticks_ms, ticks_add, ticks_diff, sleep_ms, Resource
from shell import Shell
from keyboard import Keyboard
from writer_fast import CWriter
sys.path.insert(0, "/bin")
sys.path.append("/")

if machine:
    machine.freq(250000000, 250000000)
    print("freq: %s mhz" % (machine.freq() / 1000000))
if microcontroller:
    microcontroller.cpu.frequency = 250000000
    print("freq: %s mhz" % (microcontroller.cpu.frequency / 1000000))


def monitor(task, name, scheduler = None, display_id = None):
    while True:
        gc.collect()
        ram_free = gc.mem_free()
        ram_used = gc.mem_alloc()
        ram_total = ram_free + ram_used
        #print(int(100 - (gc.mem_free() * 100 / (264 * 1024))), gc.mem_free())
        monitor_msg = "CPU%s:%3d%%  RAM:%3d%%" % (scheduler.cpu, int(100 - scheduler.idle), int(100 - (scheduler.mem_free() * 100 / ram_total)))
        print(monitor_msg)
        #print(len(scheduler.tasks))
        #scheduler.add_task(Task.get().load(free.main, "test", condition = Condition.get(), kwargs = {"args": [], "shell_id": scheduler.shell_id}))
        monitor_msg = "R%6.2f%%|F%7.2fk/%d|U%7.2fk/%d" % (100.0 - (ram_free * 100 / ram_total),
                                                          ram_free / 1024,
                                                          ram_free,
                                                          ram_used / 1024,
                                                          ram_used)
        print(monitor_msg)
        # print(Message.remain(), Condition.remain(), Task.remain())
        # yield Condition.get().load(sleep = 1000)
        stat = os.statvfs("/")
        size = stat[1] * stat[2]
        free = stat[0] * stat[3]
        used = size - free
        print("Total: %6.2fK, Used: %6.2fK, Free: %6.2fK" % (size / 1024.0, used / 1024.0, free / 1024.0))
        yield Condition.get().load(
            sleep = 5000
        )
        
        
def display(task, name, scheduler = None):
    try:
        cs = Pin(13, Pin.OUT, value = 1)
        dc = Pin(14, Pin.OUT)
        rst = Pin(15, Pin.OUT)
        sck = Pin(10)
        mosi = Pin(11)
        spi = SPI(1, baudrate = 62_500_000, sck = sck, mosi = mosi)
        lcd = ILI9488(spi, cs, dc, rst)
        lcd.fill(lcd.rgb(0, 0, 0))
        lcd.show()
        
        wri = CWriter(lcd, font8)
        wri.wrap = False
        wri.setcolor(fgcolor = lcd.rgb(1, 1, 1), bgcolor = lcd.rgb(0, 0, 0))
        line_height = 11
        
        frame_previous = None
        clear_line = const("                                                     ")
        cursor_previous = None
        while True:
            yield Condition.get().load(sleep = 0, wait_msg = True)
            msg = task.get_message()
            while True:
                try:
                    refresh = False
                    if "clear" in msg.content:
                        lcd.fill(lcd.rgb(0, 0, 0))
                    if "frame" in msg.content:                   
                        frame = msg.content["frame"]
                        lines = [False for i in range(len(frame))]
                        if frame_previous:
                            if len(frame) < len(frame_previous):
                                lines = [False for i in range(len(frame_previous))]
                            for n, l in enumerate(frame):
                                if n < len(frame_previous):
                                    if l != frame_previous[n]:
                                        lines[n] = l
                                        if l == "":
                                            lines[n] = clear_line
                                else:
                                    lines[n] = l
                            if len(frame_previous) > len(frame):
                                for n in range(len(frame), len(frame_previous)):
                                    lines[n] = clear_line
                        else:
                            lines = frame
                        x = 1
                        for n, l in enumerate(lines):
                            if l:
#                                 if l == clear_line:
#                                     lcd.text(clear_line, x, n * 8, lcd.rgb(1, 1, 1))
#                                     lcd.rect(x , n * 8, x + 8 * 40, n * 8, lcd.rgb(0, 0, 0), True)
# #                                     wri.set_textpos(lcd, n, 0)
# #                                     wri.printstring(clear_line)
#                                 else:
#                                     lcd.rect(x , n * 8, x + 8 * 40, n * 8, lcd.rgb(0, 0, 0), True)
#                                     lcd.text(l, x, n * 8, lcd.rgb(1, 1, 1))
# #                                     wri.set_textpos(lcd, n, 0)
# #                                     wri.printstring(clear_line)
# #                                     wri.set_textpos(lcd, n, 0)
# #                                     wri.printstring(l)
#                                 t = ticks_ms()
                                if l == clear_line:
                                    CWriter.set_textpos(lcd, n * line_height + 1, x)
#                                     wri.printstring(clear_line)
                                    wri.clear_line(53)
                                else:
                                    CWriter.set_textpos(lcd, n * line_height + 1, x)
#                                     wri.printstring(clear_line)
                                    wri.clear_line(53)
#                                     CWriter.set_textpos(lcd, n * 8 + 1, x)
                                    wri.printstring(l)
#                                 tt = ticks_ms()
#                                 print("update line: ", tt - t)
                        refresh = True
                        frame_previous = frame
                    if "cursor" in msg.content:
                        refresh = True
                        x, y, c = msg.content["cursor"]
                        if c == "hide":
                            lcd.line(x * 6, y * line_height, x * 6, y * line_height + line_height - 3, lcd.rgb(0, 0, 0))
                        else:
                            if cursor_previous:
                                xp, yp, cp = cursor_previous
                                lcd.line(xp * 6, yp * line_height, xp * 6, yp * line_height + line_height - 3, lcd.rgb(0, 0, 0))
                            lcd.line(x * 6, y * line_height, x * 6, y * line_height + line_height - 3, lcd.rgb(1, 1, 1) if c else lcd.rgb(0, 0, 0))
                            cursor_previous = [x, y, c]
    #                 if "keyboard_mode" in msg.content:
    #                     keyboard_mode = msg.content["keyboard_mode"]
    #                     if keyboard_mode == "DF":
    #                         lcd.line(1, 127, 10, 127, 0)
    #                     elif keyboard_mode == "SH":
    #                         lcd.line(1, 127, 5, 127, 1)
    #                     elif keyboard_mode == "CP":
    #                         lcd.line(6, 127, 10, 127, 1)
                    if refresh:
                        lcd.show()
                    msg.release()
                    break
                except Exception as e:
                    msg.release()
                    sys.print_exception(e)
    except Exception as e:
        sys.print_exception(e)
        
        
def storage(task, name, scheduler = None):
    spi = SPI(0, baudrate=13200000, sck=Pin(18), mosi=Pin(19), miso=Pin(16))
    sd = None
    vfs = None
    try:
        sd = sdcard.SDCard(spi, Pin(17), baudrate=13200000)
        vfs = uos.VfsFat(sd)
        uos.mount(vfs, "/sd")
#         print(uos.listdir("/sd"))
    except Exception as e:
        print(e)
    while True:
        yield Condition.get().load(sleep = 0, wait_msg = True)
        msg = task.get_message()
        try:
            if "cmd" in msg.content:
                cmd = msg.content["cmd"]
                args = cmd.split(" ")
                module = args[0].split(".")[0]
                #if "/sd/usr" not in sys.path:
                #    sys.path.insert(0, "/sd/usr")
                if module not in sys.modules:
                    import_str = "import %s; sys.modules['%s'] = %s" % (module, module, module)
                    exec(import_str)
                if module in ("mount", "umount"):
                    output, sd, vfs = sys.modules["%s" % module].main(*args[1:], shell_id = scheduler.shell_id, sd = sd, vfs = vfs, spi = spi, sd_cs = sd_cs)
                else:
                    output = sys.modules["%s" % module].main(*args[1:], shell_id = scheduler.shell_id, scheduler = scheduler)
                exec("del %s" % module)
                del sys.modules["%s" % module].main
                del sys.modules["%s" % module]
                gc.collect()
                yield Condition.get().load(sleep = 0, send_msgs = [
                    Message.get().load({"output": output}, receiver = scheduler.shell_id)
                ])
        except Exception as e:
            yield Condition.get().load(sleep = 0, send_msgs = [
                Message.get().load({"output": str(e)}, receiver = scheduler.shell_id)
            ])
        msg.release()
        
        
def cursor(task, name, interval = 500, s = None, display_id = None, storage_id = None):
    flash = 0
    enabled = True
    while True:
        msg = task.get_message()
        if msg:
            if msg.content["enabled"]:
                enabled = True
            else:
                enabled = False
        if enabled:
            s.set_cursor_color(flash)
            if flash == 0:
                flash = 1
            else:
                flash = 0
            if s.enable_cursor:
                yield Condition.get().load(sleep = interval, send_msgs = [Message.get().load({"cursor": s.get_cursor_position()}, receiver = display_id)])
            else:
                x, y, _ = s.get_cursor_position()
                yield Condition.get().load(sleep = interval, send_msgs = [Message.get().load({"cursor": (x, y, "hide")}, receiver = display_id)])
        else:
            yield Condition.get().load(sleep = interval)
        if msg:
            msg.release()
        
        
def shell(task, name, scheduler = None, display_id = None, storage_id = None):
    yield Condition.get().load(sleep = 1000)
    s = Shell(display_size = (52, 29), cache_size = (-1, 50), history_length = 50, scheduler = scheduler, storage_id = storage_id, display_id = display_id)
    s.write_line("                 Welcome to TinyShell")
    s.write_char("\n")
    s.write_line("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890`-=~!@#$%^&*()_+[]\\{}|;':\",./<>?")
    s.write_char("\n")
    yield Condition.get().load(sleep = 0, send_msgs = [Message.get().load(s.get_display_frame(), receiver = display_id)])
    cursor_id = scheduler.add_task(Task.get().load(cursor, "cursor", kwargs = {"interval": 500, "s": s, "display_id": display_id, "storage_id": storage_id}))
    scheduler.shell = s
    s.cursor_id = cursor_id
    while True:
        yield Condition.get().load(sleep = 0, wait_msg = True)
        msg = task.get_message()
        if "clear" in msg.content:
            if not s.disable_output:
                yield Condition.get().load(sleep = 0, send_msgs = [
                    Message.get().load({"clear": True}, receiver = display_id)
                ])
                yield Condition.get().load(sleep = 0, send_msgs = [
                    Message.get().load(s.get_display_frame(), receiver = display_id)
                ])
        if "char" in msg.content:
            c = msg.content["char"]
            s.input_char(c)
            if not s.disable_output:
                yield Condition.get().load(sleep = 0, send_msgs = [
                    Message.get().load(s.get_display_frame(), receiver = display_id)
                ])
        elif "output" in msg.content:
            output = msg.content["output"]
            s.write_lines(output, end = True)
            if not s.disable_output:
                yield Condition.get().load(sleep = 0, send_msgs = [
                    Message.get().load(s.get_display_frame(), receiver = display_id)
                ])
        elif "output_part" in msg.content:
            output = msg.content["output_part"]
            s.write_lines(output, end = False)
            if not s.disable_output:
                yield Condition.get().load(sleep = 0, send_msgs = [
                    Message.get().load(s.get_display_frame(), receiver = display_id)
                ])
        elif "output_char" in msg.content:
            c = msg.content["output_char"]
            s.write_char(c)
            if not s.disable_output:
                yield Condition.get().load(sleep = 0, send_msgs = [
                    Message.get().load(s.get_display_frame(), receiver = display_id)
                ])
        elif "frame" in msg.content:
            yield Condition.get().load(sleep = 0, send_msgs = [
                Message.get().load(msg.content, receiver = display_id)
            ])
        elif "stats" in msg.content:
            s.update_stats(msg.content["stats"])
            if not s.disable_output:
                yield Condition.get().load(sleep = 0, send_msgs = [
                    Message.get().load(s.get_display_frame(), receiver = display_id)
                ])
        msg.release()
        
        
def keyboard_input(task, name, scheduler = None, interval = 50, shell_id = None, display_id = None):
    k = Keyboard()
    Resource.keyboard = k
    yield Condition.get().load(sleep = 1000)
    keys = bytearray(30)
    i = 0
    while True:
        n = k.readinto(keys)
        if n is not None:
            print("size: ", n)
            print("keys: ", keys[:n])
        if n == 1:
            key = keys[:n].decode()
            print("key: ", key)
            if scheduler.shell and scheduler.shell.session_task_id and scheduler.exists_task(scheduler.shell.session_task_id):
                yield Condition.get().load(sleep = 0, send_msgs = [Message.get().load({"msg": key, "keys": []}, receiver = scheduler.shell.session_task_id)])
            else:
                yield Condition.get().load(sleep = 0, send_msgs = [Message.get().load({"char": key}, receiver = shell_id)])
#         i += 1
#         if i > 500:
#             i = 0
#             print(k.battery_status())
        yield Condition.get().load(sleep = interval)


if __name__ == "__main__":
    try:
        led = machine.Pin("LED", machine.Pin.OUT)
        Message.init_pool(25)
        Condition.init_pool(15)
        Task.init_pool(15)
        s = Scheduler(cpu = 0)
        display_id = s.add_task(Task.get().load(display, "display", condition = Condition.get(), kwargs = {"scheduler": s}))
        monitor_id = s.add_task(Task.get().load(monitor, "monitor", condition = Condition.get(), kwargs = {"scheduler": s, "display_id": display_id}))
        storage_id = s.add_task(Task.get().load(storage, "storage", condition = Condition.get(), kwargs = {"scheduler": s}))
        shell_id = s.add_task(Task.get().load(shell, "shell", condition = Condition.get(), kwargs = {"scheduler": s, "display_id": display_id, "storage_id": storage_id}))
        s.shell_id = shell_id
        s.set_log_to(shell_id)
        keyboard_id = s.add_task(Task.get().load(keyboard_input, "keyboard_input", condition = Condition.get(), kwargs = {"scheduler": s, "interval": 30, "shell_id": shell_id, "display_id": display_id}))
        led.on()
#         k = Keyboard()
#         time.sleep(1)
#         print(k.battery_status())
        # led.off()
        s.run()
    except Exception as e:
        import sys
        print("main exit: %s" % sys.print_exception(e))
    print("core0 exit")

