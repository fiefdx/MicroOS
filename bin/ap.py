# ap.py
"""
AP command line tool (coroutine based).

Supported sub-commands (typed after the word "ap" in your shell):

    ap start <ssid> [password]   - start AP (blank password => open network)
    ap stop                      - stop the AP
    ap status                    - show current AP configuration
    ap clients                   - list stations currently connected to the AP
    ap help                      - this help text
"""

# ----------------------------------------------------------------------
# The scheduler recognises this file as a coroutine when this flag is set.
# ----------------------------------------------------------------------
coroutine = True                      # <<<--- required by the scheduler

import sys
import network
from lib.apwifi import AP          # <-- low‑level helper
from lib.scheduler import Condition, Message

# ----------------------------------------------------------------------
# Small pure‑Python helpers (they do NOT touch the hardware).
# ----------------------------------------------------------------------
def _auth_name(mode: int) -> str:
    """Translate a numeric authmode to a human‑readable string."""
    mapping = {
        network.AUTH_OPEN:          "OPEN",
        network.AUTH_WEP:           "WEP",
        network.AUTH_WPA_PSK:      "WPA-PSK",
        network.AUTH_WPA2_PSK:     "WPA2-PSK",
        network.AUTH_WPA_WPA2_PSK: "WPA-WPA2-PSK",
    }
    return mapping.get(mode, f"UNKNOWN({mode})")

def _mac_to_str(mac: bytes) -> str:
    """Convert a raw MAC address (bytes) to the usual aa:bb:cc:dd:ee:ff format."""
    return ":".join("{:02x}".format(b) for b in mac)

def _usage() -> str:
    """Help text shown when the user asks for it or types an unknown command."""
    return (
        "AP command usage:\n"
        "  ap start <ssid> [password]   - start AP (blank password = open)\n"
        "  ap stop                      - stop AP\n"
        "  ap status                    - show AP configuration\n"
        "  ap clients                   - list stations connected to the AP\n"
        "  ap help                      - this help text\n"
    )

# ----------------------------------------------------------------------
# Prompt helper – yields the prompt, then collects characters until '\n'.
# Returns the typed string (without the trailing newline).
# ----------------------------------------------------------------------
def _prompt(task, shell_id, prompt_text) -> "generator":
    """Yield the prompt and then read key-presses until a newline."""
    # Show the prompt (no automatic line-break)
    yield task.condition.load(
        sleep=0,
        wait_msg=True,
        send_msgs=[Message.get().load(
            {"output_part": prompt_text},
            receiver=shell_id
        )]
    )

    typed = ""
    while True:
        msg = task.get_message()        # blocks until a key arrives
        ch = msg.content["msg"]
        if ch == "\n":                  # Enter -> finish input
            msg.release()
            break
        if ch == "\b":                  # Backspace handling
            typed = typed[:-1]
        else:
            typed += ch
        msg.release()
        # Wait for the next character – this yields back to the scheduler.
        yield task.condition.load(sleep=0, wait_msg=True)

    # `typed` is handed back to the caller via `yield from`.
    return typed

# ----------------------------------------------------------------------
# Robust extraction of a station entry.
# Handles:
#   * (mac, ip) tuples
#   * [mac, ip] lists
#   * mac bytes only (no IP yet)
#   * any sequence where the first element is a MAC address.
# Returns (mac_bytes, ip_str_or_None).  If the entry cannot be parsed,
# returns (None, None).
# ----------------------------------------------------------------------
def _extract_station(sta):
    # 1) Plain MAC-only (bytes or bytearray)
    if isinstance(sta, (bytes, bytearray)):
        return sta, None

    # 2) Lists or tuples – the common forms returned by MicroPython.
    if isinstance(sta, (list, tuple)):
        if len(sta) == 0:
            return None, None
        mac = sta[0]
        if not isinstance(mac, (bytes, bytearray)):
            return None, None
        ip = sta[1] if len(sta) > 1 else None
        if isinstance(ip, (bytes, bytearray)):
            ip = ip.decode("utf-8", "ignore")
        return mac, ip

    # 3) Anything else – give up gracefully.
    return None, None

# ----------------------------------------------------------------------
# The coroutine that the scheduler executes.
# ----------------------------------------------------------------------
def main(*args, **kwargs):
    """
    Scheduler entry point.

    * args[0] - the Task instance (exposes get_message())
    * kwargs   - shell_id (where to send output) and args (raw CLI args)
    """
    task     = args[0]                # the current Task object
    shell_id = kwargs.get("shell_id")
    cli_args = kwargs.get("args", [])

    try:
        # --------------------------------------------------------------
        # No arguments -> print the help text.
        # --------------------------------------------------------------
        if not cli_args:
            yield task.condition.load(
                sleep=0,
                send_msgs=[Message.get().load(
                    {"output": _usage()},
                    receiver=shell_id
                )]
            )
        else:
            subcmd = cli_args[0].lower()

            # ------------------------------------------------------
            # HELP
            # ------------------------------------------------------
            if subcmd == "help":
                yield task.condition.load(
                    sleep=0,
                    send_msgs=[Message.get().load(
                        {"output": _usage()},
                        receiver=shell_id
                    )]
                )

            # ------------------------------------------------------
            # START - interactive if SSID or password is missing.
            # ------------------------------------------------------
            elif subcmd == "start":
                # ----- SSID -------------------------------------------------
                if len(cli_args) >= 2:
                    ssid = cli_args[1]
                else:
                    ssid = yield from _prompt(task, shell_id, "SSID: ")

                # ----- PASSWORD --------------------------------------------
                if len(cli_args) >= 3:
                    password = cli_args[2]
                else:
                    password = yield from _prompt(
                        task, shell_id, "Password (blank = open): "
                    )

                # ----- ACTIVATE AP -----------------------------------------
                AP.start(ssid, password)

                # Tiny pause so the radio can settle while the scheduler
                # continues to run other tasks.
                yield task.condition.load(sleep=200)

                # ----- REPORT RESULT ----------------------------------------
                auth_txt = "OPEN" if password == "" else "WPA2-PSK"
                ip_cfg   = AP.wlan.ifconfig()
                out_msg = (
                    f"AP started - SSID: {ssid}\n"
                    f"Auth mode: {auth_txt}\n"
                    f"IP config: {ip_cfg}"
                )
                yield task.condition.load(
                    sleep=0,
                    send_msgs=[Message.get().load(
                        {"output": out_msg},
                        receiver=shell_id
                    )]
                )

            # ------------------------------------------------------
            # STOP
            # ------------------------------------------------------
            elif subcmd == "stop":
                AP.stop()
                yield task.condition.load(
                    sleep=0,
                    send_msgs=[Message.get().load(
                        {"output": "AP stopped"},
                        receiver=shell_id
                    )]
                )

            # ------------------------------------------------------
            # STATUS
            # ------------------------------------------------------
            elif subcmd == "status":
                st = AP.status()
                if not st["active"]:
                    out = "AP is not active"
                else:
                    essid = (
                        st["essid"].decode("utf-8")
                        if isinstance(st["essid"], (bytes, bytearray))
                        else str(st["essid"])
                    )
                    auth  = _auth_name(st["authmode"])
                    ip, mask, gw, dns = st["ifconfig"]
                    out = (
                        f"AP active:\n"
                        f"  SSID    : {essid}\n"
                        f"  Auth    : {auth}\n"
                        f"  IP      : {ip}\n"
                        f"  Netmask : {mask}\n"
                        f"  GW      : {gw}\n"
                        f"  DNS     : {dns}"
                    )
                yield task.condition.load(
                    sleep=0,
                    send_msgs=[Message.get().load(
                        {"output": out},
                        receiver=shell_id
                    )]
                )

            # ------------------------------------------------------
            # CLIENTS - list stations attached to the AP (robust version)
            # ------------------------------------------------------
            elif subcmd == "clients":
                if not AP.is_active():
                    out = "AP not active - no clients to show"
                else:
                    stations = AP.wlan.status("stations")
                    if not stations:
                        out = "No stations are currently connected"
                    else:
                        lines = [f"Connected stations ({len(stations)}):"]
                        for sta in stations:
                            mac, ip = _extract_station(sta)   # robust parsing
                            if mac is None:
                                # Unexpected entry – skip silently (or log)
                                continue
                            mac_str = _mac_to_str(mac)
                            lines.append(
                                f"- {mac_str}" + (f" @ {ip}" if ip else "")
                            )
                        out = "\n".join(lines)

                yield task.condition.load(
                    sleep=0,
                    send_msgs=[Message.get().load(
                        {"output": out},
                        receiver=shell_id
                    )]
                )

            # ------------------------------------------------------
            # UNKNOWN sub-command
            # ------------------------------------------------------
            else:
                out = f"Unknown sub-command '{subcmd}'. Use 'ap help' for usage."
                yield task.condition.load(
                    sleep=0,
                    send_msgs=[Message.get().load(
                        {"output": out},
                        receiver=shell_id
                    )]
                )

        # ----------------------------------------------------------------
        # End of coroutine – reaching the end of the function signals the
        # scheduler that the command has finished.  No explicit `return`
        # after a `yield` is required.
        # ----------------------------------------------------------------

    # --------------------------------------------------------------------
    # Unexpected exception – send the traceback back to the shell.
    # --------------------------------------------------------------------
    except Exception as exc:
        # sys.print_exception prints to the console; we only need a string.
        err_msg = f"AP command error: {exc}"
        yield task.condition.load(
            sleep=0,
            send_msgs=[Message.get().load(
                {"output": err_msg},
                receiver=shell_id
            )]
        )
