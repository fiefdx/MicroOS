from machine import Pin
from micropython import const
import neopixel

cpu_freq = const(240000000)
messages = const(50)
tasks = const(50)

display_cs = Pin(13, Pin.OUT, value = 1)
display_dc = Pin(34, Pin.OUT)
display_rst = Pin(35, Pin.OUT)
display_sck = Pin(10)
display_mosi = Pin(11)
display_spi = const(1)
display_baudrate = const(80_000_000)

keyboard_scl = Pin(15)
keyboard_sda = Pin(14)
keyboard_i2c = const(1)
keyboard_baudrate = const(100000)

sd_cs = Pin(37)
sd_sck = Pin(38)
sd_mosi = Pin(39)
sd_miso = Pin(36)
sd_spi = const(2)
sd_baudrate = const(80_000_000)

pwm_left = Pin(6)
pwm_right = Pin(7)

rtc_scl = Pin(41)
rtc_sda = Pin(8)
rtc_freq = 4000

ntp_delta = const(3155673600 + 3600 * 7)

class led(object):
    np = neopixel.NeoPixel(Pin(9), 1)
    
    @classmethod
    def on(cls):
        cls.np[0] = (0, 1, 0)
        cls.np.write()
        
    @classmethod
    def off(cls):
        cls.np[0] = (0, 0, 0)
        cls.np.write()
