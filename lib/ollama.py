import os
import time
import json
import request as requests


def json_to_python(s):
    if s[0] == '"' and s[-1] == '"':
        s = s[1:-1]

    s = s.replace('\\n', '\n') \
         .replace('\\r', '\r') \
         .replace('\\t', '\t') \
         .replace('\\"', '"') \
         .replace('\\\\', '\\')
    return s


def json_to_string(s):
    n_in = len(s)
    if n_in < 2:
        return s

    # pass 1: count decoded length
    i = 1
    end = n_in - 1
    n = 2   # keep start and end chars

    while i < end:
        if s[i] == '\\':
            i += 2
        else:
            i += 1
        n += 1

    # pass 2: fill buffer
    buf = bytearray(n)

    # keep start char
    buf[0] = ord(s[0])

    j = 1
    i = 1

    while i < end:
        c = s[i]
        if c == '\\':
            i += 1
            c = s[i]
            if c == 'n':   buf[j] = 10
            elif c == 'r': buf[j] = 13
            elif c == 't': buf[j] = 9
            elif c == '"': buf[j] = 34
            elif c == '\\':buf[j] = 92
            else:          buf[j] = ord(c)
        else:
            buf[j] = ord(c)
        j += 1
        i += 1

    # keep end char
    buf[j] = ord(s[-1])

    return buf.decode()



class ContextFile(object):
    def __init__(self, file_path):
        self.file_path = file_path
        
    def append(self, message = "{}"):
        with open(self.file_path, "a+") as f:
            line = message + ",\n"
            f.write(line)
            f.flush()
        
    def iter_lines(self):
        with open(self.file_path, "rb") as f:
            line = f.readline()
            while line:
                next_line = f.readline()
                if next_line:
                    yield line
                else:
                    yield line[:-2]
                line = next_line
                
    def length(self):
        result = 0
        with open(self.file_path, "rb") as f:
            f.seek(0, 2)
            result = f.tell() - 2
        return result
    
    def clear(self):
        with open(self.file_path, "wb") as f:
            pass
                
                
class ChatData(object):
    def __init__(self, file_path, model, stream = False):
        self.head = b'{"model":"%s", "messages":[' % model
        self.context_file = ContextFile(file_path)
        self.tail = b'],"stream":%s}' % ('true' if stream else 'false')
        
    def length(self):
        return len(self.head) + len(self.tail) + self.context_file.length()
        
    def iter_lines(self):
        yield self.head
        for line in self.context_file.iter_lines():
            yield line
        yield self.tail
        
    def append_message(self, message = "{}"):
        self.context_file.append(message)
        
    def clear(self):
        self.context_file.clear()


class ChatRAM(object):
    def __init__(self, host, port, model, context_length = 10, timeout = 3600, stream = False):
        self.host = host
        self.port = port
        self.model = model
        self.timeout = timeout
        self.stream = stream
        self.context_length = context_length
        self.context = []
        self.data = ChatData("/chat.data.txt", self.model, self.stream)
        self.headers = {"Content-Type": "application/json"}
        
    def models(self):
        url = "http://%s:%s/api/tags" % (self.host, self.port)
        r = requests.get(url)
        if r.status_code == 200:
            models = []
            for m in r.json()["models"]:
                models.append(m["name"])
            return True, models
        else:
            return False, r.reason

    def chat(self, message):
        url = "http://%s:%s/api/chat" % (self.host, self.port)
        message = message + " please, reply with only text, without emoji"
        self.context.append({"role": "user", "content": message})
        if len(self.context) > self.context_length:
            self.context.pop(0)
        data = {"model": self.model, "messages": self.context, "stream": self.stream}
        r = requests.post(url, data = json.dumps(data), headers = self.headers, stream = self.stream)
        if r.status_code == 200:
            if self.stream:
                result = b""
                line = r.raw.readline()
                while line:
                    result += line
                    line = r.raw.readline()
                return True, result
            else:
                response = r.json()
                self.context.append({"role": response["message"]["role"], "content": response["message"]["content"]})
                if len(self.context) > self.context_length:
                    self.context.pop(0)
                return True, response["message"]["content"]
        else:
            return False, r.reason
        
        
class Chat(object):
    def __init__(self, host, port, model, context_length = 10, timeout = 3600, stream = False, cache_file = "/.chat.cache.txt"):
        self.host = host
        self.port = port
        self.model = model
        self.timeout = timeout
        self.stream = stream
        self.context_length = context_length
        self.data = ChatData(cache_file, self.model, self.stream)
        self.content = bytearray()
        self.role = bytearray()
        self.name = bytearray()
        self.headers = {"Content-Type": "application/json"}
        
    def change_cache_file(self, cache_file):
        self.data = ChatData(cache_file, self.model, self.stream)
        
    def models(self):
        url = "http://%s:%s/api/tags" % (self.host, self.port)
        r = requests.get(url)
        models = []
        if r.status_code == 200:
            mark = '"name":"'
            mark_i = 0
            status = "end"
            for c in r.iter_chars():
                if status == "end":
                    if c == ord(mark[0]):
                        status = "mark_start"
                        mark_i = 1
                elif status == "mark_start":
                    if c == ord(mark[mark_i]):
                        mark_i += 1
                        if mark_i == len(mark):
                            status = "name_start"
                    else:
                        status = "end"
                elif status == "name_start":
                    if c == ord('"'):
                        status = "end"
                        models.append(self.name.decode())
                        self.name[:] = b''
                    else:
                        self.name.append(c)
            r.close()
            return True, models
        else:
            r.close()
            return False, r.reason
        
    def chat(self, message):
        url = "http://%s:%s/api/chat" % (self.host, self.port)
        message = message + " please, reply with only text, without emoji"
        self.data.append_message(b'{"role": "user", "content": "%s"}' % message)
        r = requests.post(url, data = self.data, headers = self.headers, stream = self.stream)
        if r.status_code == 200:
            if self.stream:
                result = b""
                line = r.raw.readline()
                while line:
                    result += line
                    line = r.raw.readline()
                r.close()
                return True, result
            else:
                mark_role = 'role":"'
                mark_role_i = 0
                mark_content = 'content":"'
                mark_content_i = 0
                mark_escape = '\\'

                last_c = ''
                status = "end"
                for c in r.iter_chars():
                    if status == "end":
                        if c == ord(mark_role[0]):
                            status = "mark_role_start"
                            mark_role_i = 1
                        elif c == ord(mark_content[0]):
                            status = "mark_content_start"
                            mark_content_i = 1
                    elif status == "mark_role_start":
                        if c == ord(mark_role[mark_role_i]):
                            mark_role_i += 1
                            if mark_role_i == len(mark_role):
                                status = "role_start"
                        else:
                            status = "end"
                    elif status == "mark_content_start":
                        if c == ord(mark_content[mark_content_i]):
                            mark_content_i += 1
                            if mark_content_i == len(mark_content):
                                status = "content_start"
                        else:
                            status = "end"
                    elif status == "role_start":
                        if c == ord('"') and last_c != ord(mark_escape):
                            status = "end"
                        else:
                            self.role.append(c)
                            last_c = c
                    elif status == "content_start":
                        if c == ord('"') and last_c != ord(mark_escape):
                            status = "end"
                        else:
                            self.content.append(c)
                            last_c = c
                content = self.content.decode()
                self.data.append_message(b'{"role": "%s", "content": "%s"}' % (self.role.decode(), content))
                self.content[:] = b''
                self.role[:] = b''
                r.close()
                return True, json_to_string(content)# json.loads(b'["%s"]' % content.decode())[0]
        else:
            r.close()
            return False, r.reason

    def clear(self):
        self.data.clear()
        self.content[:] = b''
        self.role[:] = b''
