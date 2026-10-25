"""
Python port of epoberezkin/json-source-map
Author of original JS: Evgeny Poberezkin (creator of Ajv)

Provides:
1. parse(source):
   - Streaming character-by-character recursive descent parser.
   - Tracks line, column, and pos (byte/char offset).
   - Generates exact RFC 6901 JSON Pointers (/entry/0/resource/status).
   - Returns { "data": parsed_obj, "pointers": pointer_map }.
   - Pointer map format:
     {
       "/ptr": {
         "key": { "line": int, "column": int, "pos": int },
         "keyEnd": { "line": int, "column": int, "pos": int },
         "value": { "line": int, "column": int, "pos": int },
         "valueEnd": { "line": int, "column": int, "pos": int }
       }
     }

2. stringify(data, space=2):
   - Symmetrically stringifies Python data into formatted JSON
     while simultaneously computing the RFC 6901 source map in a single pass.
   - Returns { "json": formatted_json_str, "pointers": pointer_map }.
"""

from typing import Any, Dict, List, Optional, Tuple, Union

ESCAPED_CHARS = {
    'b': '\b',
    'f': '\f',
    'n': '\n',
    'r': '\r',
    't': '\t',
    '"': '"',
    '/': '/',
    '\\': '\\'
}

def escape_json_pointer(s: str) -> str:
    """RFC 6901 escaping: ~ must be replaced before /"""
    return s.replace('~', '~0').replace('/', '~1')

def unescape_json_pointer(ptr: str) -> str:
    """RFC 6901 unescaping: / must be restored before ~"""
    return ptr.replace('~1', '/').replace('~0', '~')

def parse(source: str) -> Dict[str, Any]:
    """
    Parses JSON text character-by-character, building the parsed object
    and an exact RFC 6901 JSON pointer source map.
    """
    pos = 0
    line = 0
    column = 0
    pointers: Dict[str, Dict[str, Any]] = {}
    source_len = len(source)

    def get_loc() -> Dict[str, int]:
        return {"line": line, "column": column, "pos": pos}

    def map_loc(ptr: str, prop: str, loc: Dict[str, int]):
        if ptr not in pointers:
            pointers[ptr] = {}
        pointers[ptr][prop] = loc

    def map_pos(ptr: str, prop: str):
        map_loc(ptr, prop, get_loc())

    def check_unexpected_end():
        if pos >= source_len:
            raise ValueError(f"Unexpected end of JSON input at position {pos}")

    def get_char() -> str:
        nonlocal pos, column
        check_unexpected_end()
        ch = source[pos]
        pos += 1
        column += 1
        return ch

    def back_char():
        nonlocal pos, column
        pos -= 1
        column -= 1

    def whitespace():
        nonlocal pos, line, column
        while pos < source_len:
            ch = source[pos]
            if ch == ' ':
                column += 1
            elif ch == '\t':
                column += 4
            elif ch == '\r':
                column = 0
            elif ch == '\n':
                column = 0
                line += 1
            else:
                break
            pos += 1

    def read_exact(expected: str):
        for exp_ch in expected:
            if get_char() != exp_ch:
                raise ValueError(f"Unexpected token in JSON at position {pos - 1}")

    def parse_string() -> str:
        res = []
        while True:
            ch = get_char()
            if ch == '"':
                break
            elif ch == '\\':
                esc = get_char()
                if esc in ESCAPED_CHARS:
                    res.append(ESCAPED_CHARS[esc])
                elif esc == 'u':
                    # 4 hex digits
                    hex_digits = "".join(get_char() for _ in range(4))
                    try:
                        res.append(chr(int(hex_digits, 16)))
                    except ValueError:
                        raise ValueError(f"Bad unicode escape sequence \\u{hex_digits} at position {pos}")
                else:
                    raise ValueError(f"Bad escaped character \\{esc} at position {pos}")
            else:
                res.append(ch)
        return "".join(res)

    def parse_number() -> Union[int, float]:
        nonlocal pos
        start_p = pos
        if source[pos] == '-':
            pos += 1
        while pos < source_len and '0' <= source[pos] <= '9':
            pos += 1
        if pos < source_len and source[pos] == '.':
            pos += 1
            while pos < source_len and '0' <= source[pos] <= '9':
                pos += 1
        if pos < source_len and source[pos] in ('e', 'E'):
            pos += 1
            if pos < source_len and source[pos] in ('+', '-'):
                pos += 1
            while pos < source_len and '0' <= source[pos] <= '9':
                pos += 1
        
        num_str = source[start_p:pos]
        # sync column
        nonlocal column
        column += len(num_str)
        try:
            if '.' in num_str or 'e' in num_str or 'E' in num_str:
                return float(num_str)
            return int(num_str)
        except ValueError:
            raise ValueError(f"Invalid JSON number '{num_str}' at position {start_p}")

    def parse_array(ptr: str) -> List[Any]:
        whitespace()
        arr = []
        ch = get_char()
        if ch == ']':
            return arr
        back_char()

        i = 0
        while True:
            item_ptr = f"{ptr}/{i}"
            arr.append(_parse(item_ptr))
            whitespace()
            next_ch = get_char()
            if next_ch == ']':
                break
            if next_ch != ',':
                raise ValueError(f"Expected ',' or ']' after array element at position {pos - 1}")
            whitespace()
            i += 1
        return arr

    def parse_object(ptr: str) -> Dict[str, Any]:
        whitespace()
        obj = {}
        ch = get_char()
        if ch == '}':
            return obj
        back_char()

        while True:
            loc = get_loc()
            if get_char() != '"':
                raise ValueError(f"Expected property name string at position {pos - 1}")
            key = parse_string()
            prop_ptr = f"{ptr}/{escape_json_pointer(key)}"
            map_loc(prop_ptr, 'key', loc)
            map_pos(prop_ptr, 'keyEnd')

            whitespace()
            if get_char() != ':':
                raise ValueError(f"Expected ':' after property name at position {pos - 1}")
            whitespace()

            obj[key] = _parse(prop_ptr)
            whitespace()
            next_ch = get_char()
            if next_ch == '}':
                break
            if next_ch != ',':
                raise ValueError(f"Expected ',' or '}}' after property value at position {pos - 1}")
            whitespace()
        return obj

    def _parse(ptr: str, top_level: bool = False) -> Any:
        whitespace()
        map_pos(ptr, 'value')
        ch = get_char()

        if ch == 't':
            read_exact('rue')
            data = True
        elif ch == 'f':
            read_exact('alse')
            data = False
        elif ch == 'n':
            read_exact('ull')
            data = None
        elif ch == '"':
            data = parse_string()
        elif ch == '[':
            data = parse_array(ptr)
        elif ch == '{':
            data = parse_object(ptr)
        else:
            back_char()
            if ch in '-0123456789':
                data = parse_number()
            else:
                raise ValueError(f"Unexpected token '{ch}' at line {line + 1}, column {column + 1}, pos {pos}")

        map_pos(ptr, 'valueEnd')
        whitespace()
        if top_level and pos < source_len:
            raise ValueError(f"Unexpected trailing tokens at position {pos}")
        return data

    parsed_data = _parse('', top_level=True)
    return {
        "data": parsed_data,
        "pointers": pointers
    }

def stringify(data: Any, space: Union[int, str] = 2) -> Dict[str, Any]:
    """
    Symmetrically serializes Python data to formatted JSON string
    while constructing the exact RFC 6901 source map in a single pass.
    """
    json_chunks = []
    pointers: Dict[str, Dict[str, Any]] = {}
    line = 0
    column = 0
    pos = 0

    indent_str = " " * space if isinstance(space, int) else (space if isinstance(space, str) else "")

    def map_pos(ptr: str, prop: str):
        if ptr not in pointers:
            pointers[ptr] = {}
        pointers[ptr][prop] = {
            "line": line,
            "column": column,
            "pos": pos
        }

    def out(s: str):
        nonlocal pos, column
        json_chunks.append(s)
        pos += len(s)
        column += len(s)

    def write_indent(lvl: int):
        nonlocal line, column, pos
        if indent_str:
            nl_str = "\n" + (indent_str * lvl)
            json_chunks.append(nl_str)
            line += 1
            column = len(indent_str) * lvl
            pos += len(nl_str)

    def quoted(s: str) -> str:
        esc = s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
        return f'"{esc}"'

    def _stringify(val: Any, lvl: int, ptr: str):
        map_pos(ptr, 'value')

        if val is None:
            out('null')
        elif isinstance(val, bool):
            out('true' if val else 'false')
        elif isinstance(val, (int, float)):
            out(str(val))
        elif isinstance(val, str):
            out(quoted(val))
        elif isinstance(val, list):
            if val:
                out('[')
                item_lvl = lvl + 1
                for i, item in enumerate(val):
                    if i > 0:
                        out(',')
                    write_indent(item_lvl)
                    item_ptr = f"{ptr}/{i}"
                    _stringify(item, item_lvl, item_ptr)
                write_indent(lvl)
                out(']')
            else:
                out('[]')
        elif isinstance(val, dict):
            keys = list(val.keys())
            if keys:
                out('{')
                prop_lvl = lvl + 1
                for i, k in enumerate(keys):
                    if i > 0:
                        out(',')
                    write_indent(prop_lvl)
                    prop_ptr = f"{ptr}/{escape_json_pointer(str(k))}"
                    map_pos(prop_ptr, 'key')
                    out(quoted(str(k)))
                    map_pos(prop_ptr, 'keyEnd')
                    out(': ')
                    _stringify(val[k], prop_lvl, prop_ptr)
                write_indent(lvl)
                out('}')
            else:
                out('{}')

        map_pos(ptr, 'valueEnd')

    _stringify(data, 0, '')
    return {
        "json": "".join(json_chunks),
        "pointers": pointers
    }
