from machine import Pin
from micropython import const

cpu_freq = const(250000000)
messages = const(25)
conditions = const(20)
tasks = const(20)

display_cs = Pin(13, Pin.OUT, value = 1)
display_dc = Pin(14, Pin.OUT)
display_rst = Pin(15, Pin.OUT)
display_sck = Pin(10)
display_mosi = Pin(11)
display_spi = const(1)
display_baudrate = const(62_500_000)

keyboard_scl = Pin(7)
keyboard_sda = Pin(6)
keyboard_i2c = const(1)
keyboard_baudrate = const(100_000)

sd_cs = Pin(17)
sd_sck = Pin(18)
sd_mosi = Pin(19)
sd_miso = Pin(16)
sd_spi = const(0)
sd_baudrate = const(31_250_000)

pwm_left = Pin(26)
pwm_right = Pin(27)

rtc_scl = Pin(21)
rtc_sda = Pin(28)
rtc_freq = 4000

ntp_delta = const(2208988800 + 3600 * 7)

led = Pin("LED", Pin.OUT)