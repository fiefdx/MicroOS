import os
import sys
from io import StringIO
import urequests

from lib.scheduler import Condition, Message

coroutine = True

def main(*args, **kwargs):
    task = args[0]
    name = args[1]
    doc = """
    curl - Basic curl-like command for MicroPython
    Usage: atcurl [OPTIONS] <URL>

    Options:
      -X METHOD   HTTP method (GET, POST, PUT, DELETE, HEAD, PATCH). Default: GET
      -H HEADER   Add HTTP header (e.g., "Content-Type: application/json")
      -d DATA     Data to send in body (for POST/PUT)
      -i          Include response headers in output
      -v          Verbose mode (show request info)
      --h         Show this help
    """
    
    result = "invalid parameters"
    shell_id = kwargs["shell_id"]
    
    args = kwargs["args"]
    
    if len(args) == 0 or "--h" in args:
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": doc}, receiver = shell_id)
        ])
        return

    # Default values
    method = "GET"
    headers = {}
    data = None
    show_response_headers = False
    verbose = False
    url = None

    # Parse arguments
    i = 0
    while i < len(args):
        arg = args[i]
        
        if ">" in arg or ">>" in arg: break
        
        if arg == "-X":
            if i + 1 < len(args):
                method = args[i + 1].upper()
                i += 2
            else:
                yield task.condition.load(sleep = 0, send_msgs = [
                    Message.get().load({"output": "Error: -X requires a method"}, receiver = shell_id)
                ])
                return
                
        elif arg == "-H":
            if i + 1 < len(args):
                hdr = args[i + 1]
                if ": " in hdr:
                    key, val = hdr.split(": ", 1)
                elif ":" in hdr:
                    key, val = hdr.split(":", 1)
                    val = val.lstrip()
                else:
                    yield task.condition.load(sleep = 0, send_msgs = [
                        Message.get().load({"output": "Error: Invalid header format. Use 'Key: Value'"}, receiver = shell_id)
                    ])
                    return
                headers[key] = val
                i += 2
            else:
                yield task.condition.load(sleep = 0, send_msgs = [
                    Message.get().load({"output": "Error: -H requires a header"}, receiver = shell_id)
                ])
                return
                
        elif arg == "-d":
            if i + 1 < len(args):
                data = args[i + 1]
                i += 2
            else:
                yield task.condition.load(sleep = 0, send_msgs = [
                    Message.get().load({"output": "Error: -d requires data"}, receiver = shell_id)
                ])
                return
                
        elif arg == "-i":
            show_response_headers = True
            i += 1
            
        elif arg == "-v":
            verbose = True
            i += 1
            
        elif not arg.startswith("-"):
            if url is not None:
                yield task.condition.load(sleep = 0, send_msgs = [
                    Message.get().load({"output": "Error: Only one URL allowed"}, receiver = shell_id)
                ])
                return
            url = arg
            i += 1
            
        else:
            yield task.condition.load(sleep = 0, send_msgs = [
                Message.get().load({"output": f"Error: Unknown option: {arg}"}, receiver = shell_id)
            ])
            return

    if not url:
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": "Error: URL required\nUsage: atcurl [OPTIONS] <URL>"}, receiver = shell_id)
        ])
        return

    # Validate method
    valid_methods = {"GET", "POST", "PUT", "DELETE", "HEAD", "PATCH"}
    if method not in valid_methods:
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": f"Error: Invalid method '{method}'. Use: {', '.join(valid_methods)}"}, receiver = shell_id)
        ])
        return

    # Ensure URL has protocol
    if not url.startswith(("http://", "https://")):
        url = "http://" + url

    # Set default headers
    if "User-Agent" not in headers:
        headers["User-Agent"] = "MicroPython-atcurl/1.0"
    if "Accept" not in headers:
        headers["Accept"] = "*/*"

    # Verbose output
    if verbose:
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output_part": f"Method: {method}\nURL: {url}\nHeaders:"}, receiver = shell_id)
        ])
        for k, v in headers.items():
            yield task.condition.load(sleep = 0, send_msgs = [
                Message.get().load({"output_part": f"  {k}: {v}"}, receiver = shell_id)
            ])
        if data is not None:
            yield task.condition.load(sleep = 0, send_msgs = [
                Message.get().load({"output_part": f"Body: {data}"}, receiver = shell_id)
            ])

    try:
        # Perform request
        if method == "GET":
            resp = urequests.get(url, headers=headers)
        elif method == "POST":
            resp = urequests.post(url, data=data, headers=headers)
        elif method == "PUT":
            resp = urequests.put(url, data=data, headers=headers)
        elif method == "DELETE":
            resp = urequests.delete(url, headers=headers)
        elif method == "HEAD":
            resp = urequests.head(url, headers=headers)
        elif method == "PATCH":
            resp = urequests.patch(url, data=data, headers=headers)
        else:
            yield task.condition.load(sleep = 0, send_msgs = [
                Message.get().load({"output": f"Error: Unsupported method {method}"}, receiver = shell_id)
            ])
            return

        # Output
        output = ""
        
        if show_response_headers:
            # Format headers as string (like HTTP response)
            status_line = f"HTTP/1.1 {resp.status_code} {resp.reason.decode() if isinstance(resp.reason, bytes) else resp.reason}"
            output += status_line + "\r\n"
            for key, val in resp.headers.items():
                output += f"{key}: {val}\r\n"
            output += "\r\n"
        
        # Add body (text only; urequests.text handles decoding)
        output += resp.text
        
        #print(output, end="")
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": output}, receiver = shell_id)
        ])

        resp.close()

    except Exception as e:
        buf = StringIO()
        sys.print_exception(e, buf)
        yield task.condition.load(sleep = 0, send_msgs = [
            Message.get().load({"output": buf.getvalue()}, receiver = shell_id)
        ])