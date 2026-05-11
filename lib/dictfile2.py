import json

from .basictoken import BASICToken as Token


class CompactToken(object):
    """Lightweight token with only category and lexeme.

    Replaces BASICToken for stored/serialized tokens.
    column is dropped (only used for error display during initial parse).
    __slots__ avoids per-instance __dict__ overhead in MicroPython.
    Category constants are exposed as class attributes so the parser's
    ``token.IF``, ``token.COLON``, ``token.ELSE``, ``token.OPEN`` checks work.
    """
    __slots__ = ("category", "lexeme")

    # Expose category constants the parser accesses via token.XXX
    IF = Token.IF
    COLON = Token.COLON
    ELSE = Token.ELSE
    OPEN = Token.OPEN

    def __init__(self, category, lexeme):
        self.category = category
        self.lexeme = lexeme


def _serialize(tokens):
    """Convert a list of token-like objects to [[cat, lex], ...] for JSON."""
    return [[t.category, t.lexeme] for t in tokens]


def _deserialize(data):
    """Convert [[cat, lex], ...] from JSON to a list of CompactToken.

    Also handles legacy format from dictfile.py:
        {"d": [[col, cat, lex], ...]}  or  [[col, cat, lex], ...]
    where column is the first element (dropped).
    """
    # Handle legacy wrapper {"d": ...}
    if isinstance(data, dict) and "d" in data:
        data = data["d"]
    if not data:
        return []
    # Detect legacy 3-element (col, cat, lex) vs new 2-element (cat, lex)
    if len(data[0]) == 3:
        return [CompactToken(dd[1], dd[2]) for dd in data]
    return [CompactToken(dd[0], dd[1]) for dd in data]


class DictFile(object):
    def __init__(self, path):
        self.path = path
        self.wf = open(self.path, "w")
        self.rf = None
        self.index = {}

    def _writeline(self, line):
        pos = self.wf.tell()
        self.wf.write(line)
        self.wf.write("\n")
        self.wf.flush()
        return pos

    def keys(self):
        return self.index.keys()

    def __contains__(self, key):
        return key in self.index

    def __len__(self):
        return len(self.index)

    def __getitem__(self, key):
        if key in self.index:
            pos = self.index[key]
            if self.rf is None:
                self.rf = open(self.path, "r")
            self.rf.seek(pos, 0)
            raw = self.rf.readline()
            data = json.loads(raw.strip())
            return _deserialize(data)
        return None

    def __delitem__(self, key):
        del self.index[key]

    def get(self, key):
        return self.__getitem__(key)

    def __setitem__(self, key, tokens):
        line = json.dumps(_serialize(tokens))
        pos = self._writeline(line)
        self.index[key] = pos
        if self.rf:
            self.rf.close()
        self.rf = None

    def clear(self):
        self.index.clear()
        self.wf.close()
        self.wf = open(self.path, "w")
        if self.rf:
            self.rf.close()
        self.rf = None


class DictFileSlow(object):
    def __init__(self, path, max_line_num=6000):
        self.max_line_num = max_line_num
        self.path = path
        self.index_path = path + ".idx"
        self.wf = open(path, "w")
        self.rf = None
        with open(self.index_path, "wb") as fp:
            for _ in range(max_line_num // 40):
                fp.write(b'\xff\xff' * 40)
        self.rf_idx = open(self.index_path, "r+b")
        self.index = set()

    def _writeline(self, line):
        pos = self.wf.tell()
        self.wf.write(line)
        self.wf.write("\n")
        self.wf.flush()
        return pos

    def keys(self):
        return self.index

    def __contains__(self, key):
        return key in self.index

    def __len__(self):
        return len(self.index)

    def __getitem__(self, key):
        self.rf_idx.seek(int(key) * 2, 0)
        b = self.rf_idx.read(2)
        if b != b'\xff\xff':
            pos = int.from_bytes(b)
            if self.rf is None:
                self.rf = open(self.path, "r")
            self.rf.seek(pos, 0)
            raw = self.rf.readline()
            data = json.loads(raw.strip())
            return _deserialize(data)
        return None

    def __delitem__(self, key):
        if key in self.index:
            self.index.remove(key)

    def get(self, key):
        return self.__getitem__(key)

    def __setitem__(self, key, tokens):
        if key not in self.index:
            self.index.add(key)
        line = json.dumps(_serialize(tokens))
        pos = self._writeline(line)
        self.rf_idx.seek(int(key) * 2, 0)
        self.rf_idx.write(pos.to_bytes(2))
        if self.rf:
            self.rf.close()
        self.rf = None

    def clear(self):
        self.wf.close()
        self.wf = open(self.path, "w")
        with open(self.index_path, "wb") as fp:
            for _ in range(self.max_line_num // 40):
                fp.write(b'\xff\xff' * 40)
        if self.rf:
            self.rf.close()
        self.rf = None
        self.rf_idx = open(self.index_path, "r+b")
        self.index = set()
