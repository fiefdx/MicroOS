import os
import sys
import gc
import time
from time import ticks_ms, ticks_add, ticks_diff, sleep_ms
import uos
import framebuf
import socket
from io import StringIO
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
from machine import Pin, SPI, PWM, SoftI2C
from micropython import const

import lib
from lib import sdcard
# import font8
# import font7
from lib.display import ILI9488, Colors as C
from lib.scheduler import Scheduler, Condition, Task, Message
from lib.common import Resource, Time, exists, mkdirs, KEYS_MAP
from lib.shell import Shell
from lib.keyboard import Keyboard
import settings_pico2 as settings
# import settings_esp32s2 as settings
from lib import ntp
ntp.ntp_delta = settings.ntp_delta
if hasattr(settings, "rtc_sda"):
    from lib.urtc import DS1307
    i2c = SoftI2C(scl = settings.rtc_scl, sda = settings.rtc_sda, freq = settings.rtc_freq)
    time.sleep_ms(500)
    Time.rtc = DS1307(i2c)
    Time.sync_machine_rtc()
    
# from writer_fast import CWriter
sys.path.insert(0, "/bin")
sys.path.append("/")

if machine:
    if os.uname().nodename == "esp32":
        machine.freq(settings.cpu_freq)
    else:
        machine.freq(settings.cpu_freq, settings.cpu_freq)
    print("freq: %s mhz" % (machine.freq() / 1000000))
if microcontroller:
    microcontroller.cpu.frequency = 250000000
    print("freq: %s mhz" % (microcontroller.cpu.frequency / 1000000))

tile_defs = {}  # cache for tile bitmaps


def monitor(task, name, scheduler = None, display_id = None):
    yield task.condition.load(sleep = 3000)
    n = 0
    ram_free = 0
    ram_used = 0
    ram_total = 0
    size = 0
    free = 0
    used = 0
    plugged_in = False
    level = 0
    while True:
        try:
            gc.collect()
            if n % 2 == 0:
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
#             if n % 10 == 0:
#                 stat = os.statvfs("/")
#                 size = stat[1] * stat[2]
#                 free = stat[0] * stat[3]
#                 used = size - free
    #         print("Total: %6.2fK, Used: %6.2fK, Free: %6.2fK" % (size / 1024.0, used / 1024.0, free / 1024.0))
    #         yield task.condition.load(
    #             sleep = 2000
    #         )
#             if n % 5 == 0:
#                 if Resource.keyboard:
#                     b = Resource.keyboard.battery_status()
#                     plugged_in = b["charging"]
#                     level = b["level"]
            n += 1
            if n >= 20:
                n = 0
            yield task.condition.load(
                sleep = 1000,
                send_msgs = [Message.get().load(
                    {"stats": (scheduler.cpu, int(100 - scheduler.idle), 100.0 - (ram_free * 100 / (ram_total)), ram_free, ram_used, size, free, used, plugged_in, level)},
                    receiver = scheduler.current_shell_id
                )]
            )
        except Exception as e:
            buf = StringIO()
            sys.print_exception(e, buf)
            reason = buf.getvalue()
            print(reason)
            del buf


def render_bricks(name, msg, lcd):
    offset_x = msg.content[name]["offset_x"]
    offset_y = msg.content[name]["offset_y"]
    width = msg.content[name]["width"]
    height = msg.content[name]["height"]
    brick_size = msg.content[name]["size"]
    data = msg.content[name]["data"]
    for w in range(width):
        x = w * brick_size + offset_x
        for h in range(height):
            y = h * brick_size + offset_y
            if data[h][w] == "o":
                lcd.rect(x, y, brick_size, brick_size, C.black)
                lcd.rect(x + 2, y + 2, brick_size - 4, brick_size - 4, C.black)
            elif data[h][w] == "x":
                lcd.rect(x, y, brick_size, brick_size, C.white)
                lcd.rect(x + 2, y + 2, brick_size - 4, brick_size - 4, C.white)
#     if brick_size == 6:
#         for w in range(width):
#             x = w * brick_size + offset_x
#             for h in range(height):
#                 y = h * brick_size + offset_y
#                 if data[h][w] == "o":
#                     lcd.rect(x, y, brick_size, brick_size, C.black)
#                 elif data[h][w] == "x":
#                     lcd.rect(x, y, brick_size, brick_size, C.white)
#     elif brick_size == 4:
#         for w in range(width):
#             x = w * brick_size + offset_x
#             for h in range(height):
#                 y = h * brick_size + offset_y
#                 if data[h][w] == "o":
#                     lcd.rect(x, y, brick_size, brick_size, C.black)
#                 elif data[h][w] == "x":
#                     lcd.rect(x, y, brick_size, brick_size, C.white)


def render_texts(name, msg, lcd):
    for text in msg.content[name]:
        x = text["x"]
        y = text["y"]
        c = text["c"]
        s = text["s"]
        color = text["C"] if "C" in text else 0
        if isinstance(c, int):
            lcd.clear_line(x, y, C.black, line_height = 8, width_offset = -2, x_offset = 1, y_offset = 0, length = c)
        if isinstance(s, int):
            lcd.clear_line(x, y, C.black, line_height = 8, width_offset = -2, x_offset = 1, y_offset = 0, length = s)
        else:
            lcd.text(s, x, y, color)


def render_lines(name, msg, lcd):
    for line in msg.content[name]:
        xs, ys, xe, ye, color = line
        lcd.line(xs, ys, xe, ye, color)


def render_rects(name, msg, lcd):
    for rect in msg.content[name]:
        x, y, w, h, color = rect
        lcd.rect(x, y, w, h, color)


def render_tiles(name, msg, lcd):
    """Render a grid of tiles.
    Expected schema in msg.content[name]:
        {
            "data": [[tile_id,...], ...],   # 2-D array matching board size
            "width": int,                    # board columns (7)
            "height": int,                   # board rows (6)
            "size_w": int,                   # pixel size per tile (ignored - we use bitmap size)
            "size_h": int,
            "offset_x": int,
            "offset_y": int,
        }
    """
    spec = msg.content[name]
    data = spec["data"]
    offset_x = spec.get("offset_x", 0)
    offset_y = spec.get("offset_y", 0)
    # Tile bitmap size is taken from the cached definition
    for row_idx, row in enumerate(data):
        for col_idx, tile_id in enumerate(row):
            tile_info = tile_defs.get(tile_id)
            if tile_info:
                fb = tile_info["fb"]
                w = spec["size_w"]
                h = spec["size_h"]
                x = offset_x + col_idx * w
                y = offset_y + row_idx * h
                lcd.blit(fb, x, y)

def render_objects(name, msg, lcd):
    """Render moving objects (e.g. falling disc).
    Expected schema: list of dicts with keys "id", "x", "y".
    """
    for obj in msg.content[name]:
        tile_id = obj["id"]
        tile_info = tile_defs.get(tile_id)
        if tile_info:
            fb = tile_info["fb"]
            lcd.blit(fb, obj["x"], obj["y"])



RENDER_TABLE = {
    "bricks": render_bricks,
    "texts":  render_texts,
    "lines":  render_lines,
    "rects":  render_rects,
    "tiles":  render_tiles,
    "objects": render_objects,
}

def render(category, msg, lcd, refresh):
    name, render_type = category
    if render_type in RENDER_TABLE:
        RENDER_TABLE[render_type](*(name, msg, lcd))
        refresh = True
    return refresh

        
def display(task, name, scheduler = None):
    try:        
        spi = SPI(settings.display_spi, baudrate = settings.display_baudrate, sck = settings.display_sck, mosi = settings.display_mosi)
        lcd = ILI9488(spi, settings.display_cs, settings.display_dc, settings.display_rst)
        Resource.display = lcd
        lcd.fill(lcd.rgb(0, 0, 0))
        lcd.show()
        
        fill = lcd.fill
        rect = lcd.rect
        line = lcd.line
        text = lcd.text
        show = lcd.show
        black = C.black
        white = C.white
        green = C.green
        
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
                    if "update_tiles" in msg.content:
                        tile_defs.clear()
                        for tile in msg.content["update_tiles"]:
                            tile_id = tile["id"]
                            body = tile["body"]
                            fbuf_mono = framebuf.FrameBuffer(bytearray(body["tile"]), body["width"], body["height"], framebuf.MONO_HLSB)
                            gs8_buf = bytearray(body["width"] * body["height"])
                            fbuf_gs8 = framebuf.FrameBuffer(gs8_buf, body["width"], body["height"], framebuf.GS8)
                            palette = framebuf.FrameBuffer(bytearray(2), 2, 1, framebuf.GS8)
                            palette.pixel(0, 0, 255)   # 0-bit -> White (0xFF)
                            palette.pixel(1, 0, 0) # 1-bit -> Black (0x00)
                            # Blit mono to GS8 using the palette
                            fbuf_gs8.blit(fbuf_mono, 0, 0, -1, palette)
                            tile_defs[tile_id] = {"fb": fbuf_gs8, "w": body["width"], "h": body["height"]}
                    if "clear" in msg.content:
                        fill(black)
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
                                rect(0 , n * line_height + y_offset, 320, (n + 1) * line_height, black, True)
#                                     wri.set_textpos(lcd, n, 0)
#                                     wri.printstring(clear_line)
                            else:
                                rect(0 , n * line_height + y_offset, 320, (n + 1) * line_height, black, True)
                                if l[0] == "\x00":
                                    if l[0:3] == "\x00\x00\x00":
                                        text(">>>", x, n * line_height + y_offset, C.red)
                                        text(l[3:], x + 24, n * line_height + y_offset, white)
                                    else:
                                        text(">", x, n * line_height + y_offset, C.red)
                                        text(l[1:], x + 8, n * line_height + y_offset, white)
                                else:
                                    text(l, x, n * line_height + y_offset, white)
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
                            line(x * width + 1, (y + 1) * line_height - 3 + y_offset, (x + 1) * width - 1, (y + 1) * line_height - 3 + y_offset, black)
                        else:
                            if cursor_previous:
                                xp, yp, cp = cursor_previous
                                line(xp * width + 1, (yp + 1) * line_height - 3 + y_offset, (xp + 1) * width - 1, (yp + 1) * line_height - 3 + y_offset, black)
                            line(x * width + 1, (y + 1) * line_height - 3 + y_offset, (x + 1) * width - 1, (y + 1) * line_height - 3 + y_offset, green if c else black)
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
                        show()
                    msg.release()
                    break
                except Exception as e:
                    msg.release()
                    buf = StringIO()
                    sys.print_exception(e, buf)
                    reason = buf.getvalue()
                    print(reason)
                    del buf
    except Exception as e:
        buf = StringIO()
        sys.print_exception(e, buf)
        reason = buf.getvalue()
        print(reason)
        del buf
        
        
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
        buf = StringIO()
        sys.print_exception(e, buf)
        reason = buf.getvalue()
        print(reason)
        del buf
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
                    # import_str = "import %s; sys.modules['%s'] = %s" % (module, module, module)
                    # exec(import_str)
                    # globals()[module] = __import__(module)
                    sys.modules[module] = __import__(module) # globals()[module]
                if module in ("mount", "umount"):
                    output, sd, vfs = sys.modules["%s" % module].main(*args[1:], shell_id = scheduler.current_shell_id, sd = sd, vfs = vfs, spi = spi, sd_cs = settings.sd_cs)
                else:
                    output = sys.modules["%s" % module].main(*args[1:], shell_id = scheduler.current_shell_id, scheduler = scheduler)
                # exec("del %s" % module)
                # del globals()[module]
                del sys.modules["%s" % module].main
                del sys.modules["%s" % module]
                gc.collect()
                yield task.condition.load(sleep = 0, send_msgs = [
                    Message.get().load({"output": output}, receiver = scheduler.current_shell_id)
                ])
        except Exception as e:
            buf = StringIO()
            sys.print_exception(e, buf)
            reason = buf.getvalue()
            print(reason)
            del buf
            yield task.condition.load(sleep = 0, send_msgs = [
                Message.get().load({"output": str(e)}, receiver = scheduler.current_shell_id)
            ])
        msg.release()
        
        
def cursor(task, name, interval = 500, scheduler = None, display_id = None, storage_id = None, delay = 1500):
    msg_get = Message.get
    yield task.condition.load(sleep = delay)
    flash = 0
    enabled = True
    while True:
        msg = task.get_message()
        if msg:
            enabled = bool(msg.content.get("enabled", enabled))

        if enabled:
            scheduler.shell.set_cursor_color(flash)
            flash ^= 1
            if scheduler.shell.enable_cursor:
                payload = {"cursor": scheduler.shell.get_cursor_position()}
            else:
                x, y, _ = scheduler.shell.get_cursor_position()
                payload = {"cursor": (x, y, "hide")}
            yield task.condition.load(sleep = interval, send_msgs = [msg_get().load(payload, receiver = display_id)])
        else:
            yield task.condition.load(sleep = interval)
        if msg:
            msg.release()
        
        
def shell(task, name, shell_id = 0, scheduler = None, display_id = None, storage_id = None, delay = 1000):
    msg_get = Message.get
    yield task.condition.load(sleep = delay)
    width, height = 39, 28 # 52, 29 for 6x8 font
    s = Shell(display_size = (width, height), cache_size = (-1, 200), history_length = 100, scheduler = scheduler, storage_id = storage_id, display_id = display_id)
    s.write_line("           Welcome to TinyShell")
    s.write_char("\n")
#     s.write_line("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890`-=~!@#$%^&*()_+[]\\{}|;':\",./<>?")
#     s.write_char("\n")
    yield task.condition.load(sleep = 0, send_msgs = [msg_get().load(s.get_display_frame(), receiver = display_id)])
#     cursor_id = scheduler.add_task(Task.get().load(cursor, "cursor", kwargs = {"interval": 500, "s": s, "display_id": display_id, "storage_id": storage_id}))
#     scheduler.shell = s
    if hasattr(scheduler, "shells"):
        scheduler.shells[shell_id] = (task.id, s)
    else:
        scheduler.shells = {shell_id: (task.id, s)}
    scheduler.shell = scheduler.shells[0][1]
    scheduler.current_shell_id = scheduler.shells[0][0]
#     s.cursor_id = cursor_id
    while True:
        yield task.condition.load(sleep = 0, wait_msg = True)
        msg = task.get_message()
        if "clear" in msg.content:
            if not s.disable_output and s is scheduler.shell:
                yield task.condition.load(sleep = 0, send_msgs = [
                    msg_get().load({"clear": True}, receiver = display_id)
                ])
                yield task.condition.load(sleep = 0, send_msgs = [
                    msg_get().load(s.get_display_frame(), receiver = display_id)
                ])
        if "char" in msg.content:
            c = msg.content["char"]
            s.input_char(c)
            if not s.disable_output and s is scheduler.shell:
                yield task.condition.load(sleep = 0, wait_msg = True, send_msgs = [
                    msg_get().load(s.get_display_frame(), receiver = display_id, need_reply = True)
                ])
                r = task.get_message()
                r.release() 
        elif "output" in msg.content:
            output = msg.content["output"]
            s.write_lines(output, end = True)
            if not s.disable_output and s is scheduler.shell:
                yield task.condition.load(sleep = 0, send_msgs = [
                    msg_get().load(s.get_display_frame(), receiver = display_id)
                ])
        elif "output_part" in msg.content:
            output = msg.content["output_part"]
            s.write_lines(output, end = False)
            if not s.disable_output and s is scheduler.shell:
                yield task.condition.load(sleep = 0, send_msgs = [
                    msg_get().load(s.get_display_frame(), receiver = display_id)
                ])
        elif "output_char" in msg.content:
            c = msg.content["output_char"]
            s.write_char(c)
            if not s.disable_output and s is scheduler.shell:
                yield task.condition.load(sleep = 0, send_msgs = [
                    msg_get().load(s.get_display_frame(), receiver = display_id)
                ])
        elif "frame" in msg.content:
            if s is scheduler.shell:
                yield task.condition.load(sleep = 0, send_msgs = [
                    msg_get().load(msg.content, receiver = display_id)
                ])
        elif "stats" in msg.content:
            s.update_stats(msg.content["stats"])
            if s.disable_output:
                if scheduler.shell.current_shell and hasattr(scheduler.shell.current_shell, "get_display_frame") and not scheduler.shell.current_shell.loading:
                    yield task.condition.load(sleep = 0, send_msgs = [
                        msg_get().load(scheduler.shell.current_shell.get_display_frame(), receiver = display_id)
                    ])
            else:
                if s is scheduler.shell:
                    yield task.condition.load(sleep = 0, send_msgs = [
                        msg_get().load(s.get_display_frame(), receiver = display_id)
                    ])
            
        elif "refresh" in msg.content:
            if scheduler.shell and scheduler.shell.session_task_id and scheduler.exists_task(scheduler.shell.session_task_id):
                yield task.condition.load(sleep = 0, send_msgs = [msg_get().load({"msg": "refresh"}, receiver = scheduler.shell.session_task_id)])
            else:
                if not s.disable_output and s is scheduler.shell:
                    yield task.condition.load(sleep = 0, send_msgs = [
                        msg_get().load(s.get_display_frame(), receiver = display_id)
                    ])
        msg.release()
        
        
def keyboard_input(task, name, scheduler = None, interval = 50, display_id = None):
    k = Keyboard(settings.keyboard_scl, settings.keyboard_sda, i2c = settings.keyboard_i2c, freq = settings.keyboard_baudrate)    
    Resource.keyboard = k
    scheduler.keyboard = k  # expose keyboard for commands like connect4
    msg_get = Message.get
    yield task.condition.load(sleep = 1000)
    key_sound = const(2000)
    enable_sound = False
    keys = bytearray(30)
    
    def beep():
        return task.condition.load(sleep = 0, wait_msg = True, send_msgs = [msg_get().load({"freq": key_sound, "volume": 5000, "length": 5}, receiver = scheduler.sound_id, need_reply = True)])
    
    def switch_shell(idx):
        yield task.condition.load(sleep = 0, send_msgs = [
            msg_get().load({"clear": True}, receiver = display_id)
        ])
        scheduler.shell = scheduler.shells[idx][1]
        scheduler.current_shell_id = scheduler.shells[idx][0]
        scheduler.set_log_to(scheduler.current_shell_id)
        yield task.condition.load(sleep = 0, send_msgs = [msg_get().load({"refresh": True}, receiver = scheduler.current_shell_id)])
    
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
                    # print("size:", n, ", code:", code)                    
                    if code == b'\x81': # F1
                        if enable_sound:
                            yield beep()
                            task.get_message().release()
                        for _ in switch_shell(0):
                            yield _
                    elif code == b'\x82': # F2
                        if enable_sound:
                            yield beep()
                            task.get_message().release()
                        for _ in switch_shell(1):
                            yield _
                    elif code == b'\x86': # F6
                        if enable_sound:
                            yield beep()
                            task.get_message().release()
                        for _ in switch_shell(2):
                            yield _
                    elif code == b'\x87': # F7
                        if enable_sound:
                            yield beep()
                            task.get_message().release()
                        for _ in switch_shell(3):
                            yield _
                    elif code == b'\r':
                        enable_sound = not enable_sound
                        if enable_sound:
                            yield beep()
                            task.get_message().release()
                    else:
                        key = KEYS_MAP.get(code)
                        if key is None:
                            continue
                        
                        shell = scheduler.shell
                        if enable_sound:
                            yield beep()
                            msg = task.get_message()
                            msg.release()
                        if shell and shell.session_task_id and scheduler.exists_task(shell.session_task_id):
                            yield task.condition.load(sleep = 0, wait_msg = True, send_msgs = [msg_get().load({"msg": key, "keys": [key]}, receiver = shell.session_task_id, need_reply = True)])
                            msg = task.get_message()
                            msg.release()
                        else:
                            yield task.condition.load(sleep = 0, wait_msg = True, send_msgs = [msg_get().load({"char": key}, receiver = scheduler.current_shell_id, need_reply = True)])
                            msg = task.get_message()
                            msg.release()
        except Exception as e:
            buf = StringIO()
            sys.print_exception(e, buf)
            reason = buf.getvalue()
            print(reason)
            del buf
        
        
def sound_output(task, name, scheduler = None):
    left_pwm = PWM(settings.pwm_left)
    right_pwm = PWM(settings.pwm_right)
    left_pwm.duty_u16(0)
    right_pwm.duty_u16(0)
    while True:
        try:
            yield task.condition.load(sleep = 0, wait_msg = True)
            msg = task.get_message()
#             left_pwm = PWM(settings.pwm_left)
#             right_pwm = PWM(settings.pwm_right)
            tone_freq = msg.content["freq"]
            tone_length = msg.content["length"]
            tone_volume = msg.content["volume"]
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
#             left_pwm.deinit()
#             right_pwm.deinit()
            msg.release()
        except Exception as e:
            buf = StringIO()
            sys.print_exception(e, buf)
            reason = buf.getvalue()
            print(reason)
            del buf


if __name__ == "__main__":
    try:
        Message.init_pool(settings.messages)
        Task.init_pool(settings.tasks)
        Time.start_at = time.time()
        if not exists("/.cache"):
            mkdirs("/.cache")
        s = Scheduler(cpu = 0)
        display_id = s.add_task(Task.get().load(display, "display", kwargs = {"scheduler": s}))
        monitor_id = s.add_task(Task.get().load(monitor, "monitor", kwargs = {"scheduler": s, "display_id": display_id}))
        storage_id = s.add_task(Task.get().load(storage, "storage", kwargs = {"scheduler": s}))
        sound_id = s.add_task(Task.get().load(sound_output, "sound_output", kwargs = {"scheduler": s}))
        s.sound_id = sound_id
        shell_id_0 = s.add_task(Task.get().load(shell, "shell:0", kwargs = {"shell_id": 0, "scheduler": s, "display_id": display_id, "storage_id": storage_id}))
        # s.shell_id = shell_id_0
        shell_id_1 = s.add_task(Task.get().load(shell, "shell:1", kwargs = {"shell_id": 1, "scheduler": s, "display_id": display_id, "storage_id": storage_id, "delay": 1200}))
        shell_id_2 = s.add_task(Task.get().load(shell, "shell:2", kwargs = {"shell_id": 2, "scheduler": s, "display_id": display_id, "storage_id": storage_id, "delay": 1200}))
        shell_id_3 = s.add_task(Task.get().load(shell, "shell:3", kwargs = {"shell_id": 3, "scheduler": s, "display_id": display_id, "storage_id": storage_id, "delay": 1200}))
        # s.shell_id = shell_id_0
        # s.set_log_to(shell_id)
        cursor_id = s.add_task(Task.get().load(cursor, "cursor", kwargs = {"interval": 500, "scheduler": s, "display_id": display_id, "storage_id": storage_id, "delay": 3000}))
        s.cursor_id = cursor_id
        keyboard_id = s.add_task(Task.get().load(keyboard_input, "keyboard_input", kwargs = {"scheduler": s, "interval": 30, "display_id": display_id}))
        settings.led.on()
        # settings.led.off()
        s.run()
    except Exception as e:
        import sys
        print("main exit: %s" % sys.print_exception(e))
    print("core0 exit")
