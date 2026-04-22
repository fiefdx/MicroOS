import os
import json


class ListFile(object):
    def __init__(self, path, shrink_threshold = 1024):
        self.path = path
        self.shrink_threshold = shrink_threshold
        self.wf = open(self.path, "w")
        self.rf = open(self.path, "r")
        self.list = []
        self.current = 0
        
    def writejson(self, d, wf = None):
        line = json.dumps(d) + "\n"
        length = len(line)
        if wf is None:
            pos = self.wf.tell()
            self.wf.write(line)
            self.wf.flush()
        else:
            pos = wf.tell()
            wf.write(line)
            wf.flush()
        return pos, length

    def append(self, value):
        pos, length = self.writejson(value)
        self.list.append(pos)
        if max(self.list) > self.shrink_threshold:
            self.shrink()
        else:
            self.rf.close()
            self.rf = open(self.path, "r")

    def pop(self, i):
        pos = self.list.pop(i)
        self.rf.seek(pos, 0)
        d = json.loads(self.rf.readline()[:-1])
        return d
    
    def __iter__(self):
        self.current = 0
        return self

    def __next__(self):
        if self.current < len(self.list):
            pos = self.list[self.current]
            self.rf.seek(pos, 0)
            d = json.loads(self.rf.readline()[:-1])
            self.current += 1
            return d
        raise StopIteration

    def __contains__(self, key):
        return False

    def __len__(self):
        return len(self.list)

    def __getitem__(self, key):
        if isinstance(key, slice):
            start = 0 if key.start is None else key.start
            if start < 0:
                start += len(self.list)
                if start < 0:
                    start = 0
                elif start >= len(self.list):
                    start = len(self.list) - 1
            elif start >= len(self.list):
                start = len(self.list)
            stop = len(self.list) if key.stop is None else key.stop
            if stop < 0:
                stop += len(self.list)
                if stop < 0:
                    stop = 0
                elif stop >= len(self.list):
                    stop = len(self.list) - 1
            elif stop >= len(self.list):
                stop = len(self.list)
            step = 1 if key.step is None else key.step
            d = []
            if start < len(self.list):
                for i in range(start, stop, step):
                    d.append(self[i])
            return d
        else:
            if key < 0:
                key += len(self.list)
                if key < 0:
                    key = 0
                elif key >= len(self.list):
                    key = len(self.list) - 1
            elif key >= len(self.list):
                key = len(self.list) - 1
            pos = self.list[key]
            self.rf.seek(pos, 0)
            d = json.loads(self.rf.readline()[:-1])
            return d
    
    def get(self, key):
        return self.__getitem__(key)

    def __setitem__(self, key, value):
        pos, length = self.writejson(value)
        self.list[key] = pos
        if max(self.list) > self.shrink_threshold:
            self.shrink()
        else:
            self.rf.close()
            self.rf = open(self.path, "r")

    def insert(self, key, value):
        pos, length = self.writejson(value)
        self.list.insert(key, pos)
        if max(self.list) > self.shrink_threshold:
            self.shrink()
        else:
            self.rf.close()
            self.rf = open(self.path, "r")

    def shrink(self):
        self.list_tmp = []
        wf = open(self.path + ".tmp", "w")
        for i in range(len(self.list)):
            v = self[i]
            pos, length = self.writejson(v, wf = wf)
            self.list_tmp.append(pos)
        self.list = self.list_tmp
        wf.flush()
        wf.close()
        self.wf.close()
        self.rf.close()
        os.remove(self.path)
        os.rename(self.path + ".tmp", self.path)
        self.wf = open(self.path, "a+")
        self.rf = open(self.path, "r")
        
    def clear(self):
        self.list.clear()
        # self.rf.close()
        # self.wf.close()
    
    def close(self):
        if hasattr(self, 'wf') and self.wf:
            self.wf.close()
        if hasattr(self, 'rf') and self.rf:
            self.rf.close()
