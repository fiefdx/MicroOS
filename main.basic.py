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

from lib.basictoken import BASICToken as Token

from lib import sdcard
# import font8
# import font7
from lib.display import ILI9488, Colors as C
from lib.scheduler import Scheduler, Condition, Task, Message
from lib.common import ticks_ms, ticks_add, ticks_diff, sleep_ms, Resource, KEYS_MAP
from lib.shell import Shell
from lib.keyboard import Keyboard
from lib.basic_shell_alone import BasicShell
import settings_pico2 as settings
# from writer_fast import CWriter
sys.path.insert(0, "/bin")
sys.path.append("/")

if machine:
    machine.freq(250000000, 250000000)
    print("freq: %s mhz" % (machine.freq() / 1000000))
if microcontroller:
    microcontroller.cpu.frequency = 250000000
    print("freq: %s mhz" % (microcontroller.cpu.frequency / 1000000))


def monitor(task, name, scheduler = None, display_id = None):
    yield task.condition.load(sleep = 2000)
    while True:
        gc.collect()
        ram_free = gc.mem_free()
        ram_used = gc.mem_alloc()
        ram_total = ram_free + ram_used
#         #print(int(100 - (gc.mem_free() * 100 / (264 * 1024))), gc.mem_free())
#         monitor_msg = "CPU%s:%3d%%  RAM:%3d%%" % (scheduler.cpu, int(100 - scheduler.idle), int(100 - (scheduler.mem_free() * 100 / ram_total)))
#         print(monitor_msg)
#         #print(len(scheduler.tasks))
#         #scheduler.add_task(Task.get().load(free.main, "test", kwargs = {"args": [], "shell_id": scheduler.shell_id}))
#         monitor_msg = "R%6.2f%%|F%7.2fk/%d|U%7.2fk/%d" % (100.0 - (ram_free * 100 / ram_total),
#                                                           ram_free / 1024,
#                                                           ram_free,
#                                                           ram_used / 1024,
#                                                           ram_used)
#         print(monitor_msg)
#         # print(Message.remain(), Task.remain())
#         # yield task.condition.load(sleep = 1000)
        stat = os.statvfs("/")
        size = stat[1] * stat[2]
        free = stat[0] * stat[3]
        used = size - free
#         print("Total: %6.2fK, Used: %6.2fK, Free: %6.2fK" % (size / 1024.0, used / 1024.0, free / 1024.0))
#         yield task.condition.load(
#             sleep = 2000
#         )
        plugged_in = False
        level = 0
        if Resource.keyboard:
            b = Resource.keyboard.battery_status()
            plugged_in = b["charging"]
            level = b["level"]
        yield task.condition.load(sleep = 1000)
#         yield task.condition.load(
#             sleep = 1000,
#             send_msgs = [Message.get().load(
#                 {"stats": (scheduler.cpu, int(100 - scheduler.idle), 100.0 - (ram_free * 100 / (ram_total)), ram_free, ram_used, size, free, used, plugged_in, level)},
#                 receiver = scheduler.shell_id
#             )]
#         )


def render_texts(name, msg, lcd):
    for text in msg.content[name]:
        x = text["x"]
        y = text["y"]
        c = text["c"]
        s = text["s"]
        color = text["C"] if "C" in text else 0
        if isinstance(c, int):
            lcd.clear_line(x, y, C.black, line_height = 8, width_offset = -2, x_offset = 1, y_offset = 0, length = c)
        lcd.text(s, x, y, color)


def render_lines(name, msg, lcd):
    for line in msg.content[name]:
        xs, ys, xe, ye, color = line
        lcd.line(xs, ys, xe, ye, color)


def render_rects(name, msg, lcd):
    for rect in msg.content[name]:
        x, y, w, h, color = rect
        lcd.rect(x, y, w, h, color)


def render(category, msg, lcd, refresh):
    name, render_type = category
    renders = {
        "texts": (render_texts, [name, msg, lcd]),
        "lines": (render_lines, [name, msg, lcd]),
        "rects": (render_rects, [name, msg, lcd]),
    }
    if render_type in renders:
        renders[render_type][0](*renders[render_type][1])
        refresh = True
    return refresh

        
def display(task, name, scheduler = None):
    try:
        spi = SPI(settings.display_spi, baudrate = settings.display_baudrate, sck = settings.display_sck, mosi = settings.display_mosi)
        lcd = ILI9488(spi, settings.display_cs, settings.display_dc, settings.display_rst)
        Resource.display = lcd
        lcd.fill(lcd.rgb(0, 0, 0))
        lcd.show()
        
#         wri = CWriter(lcd, font8)
#         wri.wrap = False
#         wri.setcolor(fgcolor = lcd.rgb(1, 1, 1), bgcolor = lcd.rgb(0, 0, 0))
        width, height = 8, 8 # 6, 8
        x_offset, y_offset = 1, 1
        line_height = 11
        
        frame_previous = None
        clear_line = const("                                                     ")
        cursor_previous = None
        while True:
            yield task.condition.load(sleep = 0, wait_msg = True)
            msg = task.get_message()
            while True:
                try:
                    refresh = False
                    if "clear" in msg.content:
                        lcd.fill(lcd.rgb(0, 0, 0))
                    if "frame" in msg.content:                   
                        frame = msg.content["frame"]
#                         lines = [False for i in range(len(frame))]
#                         if frame_previous:
#                             if len(frame) < len(frame_previous):
#                                 lines = [False for i in range(len(frame_previous))]
#                             for n, l in enumerate(frame):
#                                 if n < len(frame_previous):
#                                     if l != frame_previous[n]:
#                                         lines[n] = l
#                                         if l == "":
#                                             lines[n] = clear_line
#                                 else:
#                                     lines[n] = l
#                             if len(frame_previous) > len(frame):
#                                 for n in range(len(frame), len(frame_previous)):
#                                     lines[n] = clear_line
#                         else:
#                             lines = frame
                        lines = frame
                        x = 0
                        for n, l in enumerate(lines):
#                             if l:
                            if l == "":
#                                     lcd.text(clear_line, x, n * line_height, lcd.rgb(1, 1, 1))
                                lcd.rect(0 , n * line_height + y_offset, 320, (n + 1) * line_height, lcd.rgb(0, 0, 0), True)
#                                     wri.set_textpos(lcd, n, 0)
#                                     wri.printstring(clear_line)
                            else:
                                lcd.rect(0 , n * line_height + y_offset, 320, (n + 1) * line_height, lcd.rgb(0, 0, 0), True)
                                if l[0] == "\x00":
                                    lcd.text(">", x, n * line_height + y_offset, C.red)
                                    lcd.text(l[1:], x + 8, n * line_height + y_offset, lcd.rgb(1, 1, 1))
                                elif l[0] == "\x01":
                                    lcd.text("#", x, n * line_height + y_offset, C.red)
                                    lcd.text(l[1:], x + 8, n * line_height + y_offset, lcd.rgb(1, 1, 1))
                                else:
                                    lcd.text(l, x, n * line_height + y_offset, lcd.rgb(1, 1, 1))
#                                     wri.set_textpos(lcd, n, 0)
#                                     wri.printstring(clear_line)
#                                     wri.set_textpos(lcd, n, 0)
#                                     wri.printstring(l)
#                                 t = ticks_ms()
#                                 if l == clear_line:
#                                     CWriter.set_textpos(lcd, n * line_height + 1, x)
# #                                     wri.printstring(clear_line)
#                                     wri.clear_line(53)
#                                 else:
#                                     CWriter.set_textpos(lcd, n * line_height + 1, x)
# #                                     wri.printstring(clear_line)
#                                     wri.clear_line(53)
# #                                     CWriter.set_textpos(lcd, n * 8 + 1, x)
#                                     wri.printstring(l)
# #                                 tt = ticks_ms()
# #                                 print("update line: ", tt - t)
                        refresh = True
                        frame_previous = frame
                    if "cursor" in msg.content:
                        refresh = True
                        x, y, c = msg.content["cursor"]
                        if c == "hide":
                            lcd.line(x * width + 1, (y + 1) * line_height - 3 + y_offset, (x + 1) * width - 1, (y + 1) * line_height - 3 + y_offset, C.black)
                        else:
                            if cursor_previous:
                                xp, yp, cp = cursor_previous
                                lcd.line(xp * width + 1, (yp + 1) * line_height - 3 + y_offset, (xp + 1) * width - 1, (yp + 1) * line_height - 3 + y_offset, C.black)
                            lcd.line(x * width + 1, (y + 1) * line_height - 3 + y_offset, (x + 1) * width - 1, (y + 1) * line_height - 3 + y_offset, C.green if c else C.black)
                            cursor_previous = [x, y, c]
#                         if c == "hide":
#                             lcd.line(x * width - 1, y * line_height, x * width - 1, y * line_height + line_height - 3, lcd.rgb(0, 0, 0))
#                         else:
#                             if cursor_previous:
#                                 xp, yp, cp = cursor_previous
#                                 lcd.line(xp * width - 1, yp * line_height, xp * width - 1, yp * line_height + line_height - 3, lcd.rgb(0, 0, 0))
#                             lcd.line(x * width - 1, y * line_height, x * width - 1, y * line_height + line_height - 3, lcd.rgb(1, 1, 1) if c else lcd.rgb(0, 0, 0))
#                             cursor_previous = [x, y, c]
                    if "render" in msg.content:
                        for category in msg.content["render"]:
                            refresh = render(category, msg, lcd, refresh)
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
    spi = SPI(settings.sd_spi, baudrate = settings.sd_baudrate, sck = settings.sd_sck, mosi = settings.sd_mosi, miso = settings.sd_miso)
    sd = None
    vfs = None
    try:
        sd = sdcard.SDCard(spi, settings.sd_cs, baudrate = settings.sd_baudrate)
        vfs = uos.VfsFat(sd)
        uos.mount(vfs, "/sd")
#         print(uos.listdir("/sd"))
    except Exception as e:
        print(e)
    while True:
        yield task.condition.load(sleep = 0, wait_msg = True)
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
                    output, sd, vfs = sys.modules["%s" % module].main(*args[1:], shell_id = scheduler.current_shell_id, sd = sd, vfs = vfs, spi = spi, sd_cs = settings.sd_cs)
                else:
                    output = sys.modules["%s" % module].main(*args[1:], shell_id = scheduler.current_shell_id, scheduler = scheduler)
                exec("del %s" % module)
                del sys.modules["%s" % module].main
                del sys.modules["%s" % module]
                gc.collect()
                yield task.condition.load(sleep = 0, send_msgs = [
                    Message.get().load({"output": output}, receiver = scheduler.current_shell_id)
                ])
        except Exception as e:
            yield task.condition.load(sleep = 0, send_msgs = [
                Message.get().load({"output": str(e)}, receiver = scheduler.current_shell_id)
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
                yield task.condition.load(sleep = interval, send_msgs = [Message.get().load({"cursor": s.get_cursor_position()}, receiver = display_id)])
            else:
                x, y, _ = s.get_cursor_position()
                yield task.condition.load(sleep = interval, send_msgs = [Message.get().load({"cursor": (x, y, "hide")}, receiver = display_id)])
        else:
            yield task.condition.load(sleep = interval)
        if msg:
            msg.release()
        
        
def shell(task, name, scheduler = None, display_id = None, storage_id = None):
    yield task.condition.load(sleep = 1000)
    #s = Shell()
    try:
        s = BasicShell(display_size = (39, 29), cache_size = (-1, 50), history_length = 50, scheduler = scheduler, storage_id = storage_id, display_id = display_id)
        # print = s.print
        Token.print = s.print
        s.write_line("           Welcome to PyBASIC")
        s.write_char("\n")
        yield task.condition.load(sleep = 0, send_msgs = [Message.get().load(s.get_display_frame(), receiver = display_id)])
        cursor_id = scheduler.add_task(Task.get().load(cursor, "cursor", kwargs = {"interval": 500, "s": s, "display_id": display_id, "storage_id": storage_id}))
        scheduler.shell = s
        s.cursor_id = cursor_id
        frame_previous = None
        while True:
            yield task.condition.load(sleep = 0, wait_msg = False)
            msg = task.get_message()
            if msg:
                if "clear" in msg.content:
                    if not s.disable_output:
                        yield task.condition.load(sleep = 0, send_msgs = [
                            Message.get().load({"clear": True}, receiver = display_id)
                        ])
                        yield task.condition.load(sleep = 0, send_msgs = [
                            Message.get().load(s.get_display_frame(), receiver = display_id)
                        ])
                if "char" in msg.content:
                    c = msg.content["char"]
                    s.input_char(c)
                    if not s.disable_output:
                        yield task.condition.load(sleep = 0, send_msgs = [
                            Message.get().load(s.get_display_frame(), receiver = display_id)
                        ])
                    else:
                        data = s.get_display_frame()
                        if s.diff_frame(data["frame"], frame_previous):
                            yield task.condition.load(sleep = 0, wait_msg = False, send_msgs = [
                                Message.get().load(data, receiver = display_id)
                            ])
                            frame_previous = data["frame"]
                        else:
                            yield task.condition.load(sleep = 0, wait_msg = False)
                elif "output" in msg.content:
                    output = msg.content["output"]
                    s.write_lines(output, end = True)
                    if not s.disable_output:
                        yield task.condition.load(sleep = 0, send_msgs = [
                            Message.get().load(s.get_display_frame(), receiver = display_id)
                        ])
                elif "output_part" in msg.content:
                    output = msg.content["output_part"]
                    s.write_lines(output, end = False)
                    if not s.disable_output:
                        yield task.condition.load(sleep = 0, send_msgs = [
                            Message.get().load(s.get_display_frame(), receiver = display_id)
                        ])
                elif "output_char" in msg.content:
                    c = msg.content["output_char"]
                    s.write_char(c)
                    if not s.disable_output:
                        yield task.condition.load(sleep = 0, send_msgs = [
                            Message.get().load(s.get_display_frame(), receiver = display_id)
                        ])
                elif "frame" in msg.content:
                    yield task.condition.load(sleep = 0, send_msgs = [
                        Message.get().load(msg.content, receiver = display_id)
                    ])
                msg.release()
            else:
                data = s.get_display_frame()
                if s.diff_frame(data["frame"], frame_previous):
                    yield task.condition.load(sleep = 0, wait_msg = False, send_msgs = [
                        Message.get().load(data, receiver = display_id)
                    ])
                    frame_previous = data["frame"]
                else:
                    yield task.condition.load(sleep = 0, wait_msg = False)
    except Exception as e:
        print(sys.print_exception(e))
            
            
def keyboard_input(task, name, scheduler = None, interval = 50, shell_id = None, display_id = None):
    k = Keyboard(settings.keyboard_scl, settings.keyboard_sda, i2c = settings.keyboard_i2c, freq = settings.keyboard_baudrate)
    Resource.keyboard = k
    msg_get = Message.get
    yield task.condition.load(sleep = 1000)
    key_sound = const(2000)
    enable_sound = False
    keys = bytearray(30)

    def beep():
        return task.condition.load(sleep = 0, wait_msg = True, send_msgs = [msg_get().load({"freq": key_sound, "volume": 5000, "length": 5}, receiver = scheduler.sound_id, need_reply = True)])

    while True:
        try:
            if k.disable:
                yield task.condition.load(sleep = 1000)
                continue

            yield task.condition.load(sleep = interval)
            n = k.readinto(keys)
            if n:
                n = 1
                for i in range(n):
                    code = bytes(keys[i:i+1])
                    key = KEYS_MAP.get(code)
                    if key is None:
                        continue

                    if key == "Ctrl-M":
                        enable_sound = not enable_sound
                        if enable_sound:
                            yield beep()
                            task.get_message().release()
                    else:
                        if enable_sound:
                            yield beep()
                            task.get_message().release()
                        if scheduler.shell and scheduler.shell.session_task_id and scheduler.exists_task(scheduler.shell.session_task_id):
                            yield task.condition.load(sleep = 0, send_msgs = [msg_get().load({"msg": key, "keys": [key]}, receiver = scheduler.shell.session_task_id)])
                        else:
                            yield task.condition.load(sleep = 0, send_msgs = [msg_get().load({"char": key}, receiver = shell_id)])
        except Exception as e:
            print(e)
        
        
def sound_output(task, name, scheduler = None):
    while True:
        try:
            yield task.condition.load(sleep = 0, wait_msg = True)
            msg = task.get_message()
            tone_freq = msg.content["freq"]
            tone_length = msg.content["length"]
            tone_volume = msg.content["volume"]
            left_pwm = PWM(settings.pwm_left)
            right_pwm = PWM(settings.pwm_right)
            if tone_freq >= 20:
                left_pwm.freq(tone_freq)
                right_pwm.freq(tone_freq)
                left_pwm.duty_u16(tone_volume)
                right_pwm.duty_u16(tone_volume)
            if tone_length < 10:
                sleep_ms(tone_length)
            else:
                yield task.condition.load(sleep = tone_length)
            left_pwm.duty_u16(0)
            right_pwm.duty_u16(0)
            left_pwm.deinit()
            right_pwm.deinit()
            msg.release()
        except Exception as e:
            print(e)


if __name__ == "__main__":
    try:
        Message.init_pool(15)
        Task.init_pool(12)
        s = Scheduler(cpu = 0)
        display_id = s.add_task(Task.get().load(display, "display", kwargs = {"scheduler": s}))
        monitor_id = s.add_task(Task.get().load(monitor, "monitor", kwargs = {"scheduler": s, "display_id": display_id}))
        storage_id = s.add_task(Task.get().load(storage, "storage", kwargs = {"scheduler": s}))
        sound_id = s.add_task(Task.get().load(sound_output, "sound_output", kwargs = {"scheduler": s}))
        s.sound_id = sound_id
        shell_id = s.add_task(Task.get().load(shell, "shell", kwargs = {"scheduler": s, "display_id": display_id, "storage_id": storage_id}))
        s.shell_id = shell_id
        s.set_log_to(shell_id)
        keyboard_id = s.add_task(Task.get().load(keyboard_input, "keyboard_input", kwargs = {"scheduler": s, "interval": 30, "shell_id": shell_id, "display_id": display_id}))
        settings.led.on()
        # settings.led.off()
        s.run()
    except Exception as e:
        import sys
        print("main exit: %s" % sys.print_exception(e))
    print("core0 exit")
