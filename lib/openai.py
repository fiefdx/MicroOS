import ujson
import request as requests


class OpenAIChat(object):
    def __init__(self, host, port, model, api_key="", context_length=10):
        self.host = host
        self.port = port
        self.model = model
        self.api_key = api_key
        self.context_length = context_length
        self.context = []
        self.headers = {"Content-Type": "application/json"}
        if self.api_key:
            self.headers["Authorization"] = "Bearer " + self.api_key

    def models(self):
        url = "http://%s:%s/v1/models" % (self.host, self.port)
        r = requests.get(url)
        models = []
        if r.status_code == 200:
            try:
                data = r.json()
                for m in data.get("data", []):
                    models.append(m["id"])
            except Exception:
                r.close()
                return False, "failed to parse models response"
            r.close()
            return True, models
        else:
            r.close()
            return False, r.reason

    def chat(self, message):
        url = "http://%s:%s/v1/chat/completions" % (self.host, self.port)
        self.context.append({"role": "user", "content": message})
        if len(self.context) > self.context_length:
            self.context.pop(0)
        data = {"model": self.model, "messages": self.context}
        r = requests.post(url, data=ujson.dumps(data), headers=self.headers)
        if r.status_code == 200:
            try:
                resp = r.json()
                content = resp["choices"][0]["message"]["content"]
                self.context.append({"role": "assistant", "content": content})
                if len(self.context) > self.context_length:
                    self.context.pop(0)
            except Exception as e:
                r.close()
                return False, str(e)
            r.close()
            return True, content
        else:
            r.close()
            return False, r.reason

    def clear(self):
        self.context = []
