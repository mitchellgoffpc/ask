import sys
import re
import zlib

# Parsing helper functions

def skip_whitespace(pdf_data, i):
    while i < len(pdf_data) and pdf_data[i] in b' \t\n\r\x00':
        i += 1
    return i

def parse_name(pdf_data, i):
    if not (match := re.match(rb'/([^\s/()<>[\]{}%]+)', pdf_data[i:])):
        raise ValueError("Expected name object starting with '/'")
    name = match.group(1).decode('utf-8', 'replace')
    return name, i + match.end()

def parse_number(pdf_data, i):
    if not (match := re.match(rb'[+-]?\d*\.?\d+(?:[eE][+-]?\d+)?', pdf_data[i:])):
        raise ValueError("Expected number")
    num_str = match.group().decode('utf-8', 'replace')
    value = float(num_str) if any(c in num_str for c in '.eE') else int(num_str)
    return value, i + match.end()

def parse_boolean(pdf_data, i):
    if not (match := re.match(rb'(true|false)', pdf_data[i:])):
        raise ValueError("Expected boolean value")
    value = match.group(1) == b'true'
    return value, i + match.end()

def parse_null(pdf_data, i):
    if not (match := re.match(rb'null', pdf_data[i:])):
        raise ValueError("Expected null value")
    return None, i + match.end()

def parse_string(pdf_data, i):
    if pdf_data[i] != ord('('):
        raise ValueError("Expected string object starting with '('")
    i += 1
    start = i
    nest = 1
    while i < len(pdf_data) and nest > 0:
        if pdf_data[i] == ord('('):
            nest += 1
        elif pdf_data[i] == ord(')'):
            nest -= 1
        elif pdf_data[i] == ord('\\'):
            i += 1  # Skip escaped character
        i += 1
    string = pdf_data[start:i - 1].decode('utf-8', 'replace')
    return string, i

def parse_hex_string(pdf_data, i):
    if pdf_data[i] != ord('<'):
        raise ValueError("Expected hex string starting with '<'")
    i += 1
    start = i
    while i < len(pdf_data) and pdf_data[i] != ord('>'):
        i += 1
    hex_string = pdf_data[start:i].decode('ascii', 'replace')
    i += 1  # Skip '>'
    string = bytes.fromhex(hex_string)
    return string, i

def parse_indirect_reference(pdf_data, i):
    match = re.match(rb'\d+\s+\d+\s+R', pdf_data[i:])
    if not match:
        raise ValueError("Expected indirect reference in the form 'n n R'")
    i += match.end()
    return match.group().decode('ascii'), i

def parse_array(pdf_data, i):
    if pdf_data[i] != ord('['):
        raise ValueError("Expected array starting with '['")
    i += 1
    arr = []
    while i < len(pdf_data):
        i = skip_whitespace(pdf_data, i)
        if pdf_data[i] == ord(']'):
            i += 1
            break
        obj, i = parse_pdf_object(pdf_data, i)
        arr.append(obj)
    return arr, i

def parse_dictionary(pdf_data, i):
    if pdf_data[i:i + 2] != b'<<':
        raise ValueError("Expected dictionary starting with '<<'")
    i += 2
    d = {}
    while i < len(pdf_data):
        i = skip_whitespace(pdf_data, i)
        if pdf_data[i:i + 2] == b'>>':
            i += 2
            break
        key, i = parse_name(pdf_data, i)
        i = skip_whitespace(pdf_data, i)
        value, i = parse_pdf_object(pdf_data, i)
        d[key] = value
    return d, i

def parse_pdf_object(pdf_data, i):
    i = skip_whitespace(pdf_data, i)
    if i >= len(pdf_data):
        raise ValueError("Unexpected end of data")
    c = pdf_data[i]
    if c == ord('/'):
        return parse_name(pdf_data, i)
    elif c == ord('('):
        return parse_string(pdf_data, i)
    elif c == ord('['):
        return parse_array(pdf_data, i)
    elif c == ord('<'):
        if pdf_data[i:i + 2] == b'<<':
            return parse_dictionary(pdf_data, i)
        else:
            return parse_hex_string(pdf_data, i)
    elif pdf_data.startswith(b'null', i):
        return parse_null(pdf_data, i)
    elif pdf_data.startswith((b'true', b'false'), i):
        return parse_boolean(pdf_data, i)
    elif re.match(rb'\d+\s+\d+\s+R', pdf_data[i:]):
        return parse_indirect_reference(pdf_data, i)
    elif c in b'+-0123456789.':
        return parse_number(pdf_data, i)
    else:
        raise ValueError(f"Unknown object type at position {i}")


# Extract text from a PDF file

def tokenize_stream(data):
    tokens = []
    i = 0
    while i < len(data):
        c = data[i]
        if c in b' \t\n\r\x00':
            i += 1
            continue
        elif c == ord('%'):
            # Comment, skip to end of line
            while i < len(data) and data[i] not in b'\r\n':
                i += 1
        elif c == ord('('):
            # String object
            start = i
            i += 1
            nest = 1
            while i < len(data) and nest > 0:
                if data[i] == ord('('):
                    nest += 1
                elif data[i] == ord(')'):
                    nest -= 1
                elif data[i] == ord('\\'):
                    i += 1  # Skip escaped character
                i += 1
            tokens.append(data[start:i])
        elif c == ord('/'):
            # Name object
            start = i
            i += 1
            while i < len(data) and data[i] not in b' \t\n\r\x00/()<>[]{}%':
                i += 1
            tokens.append(data[start:i])
        elif c == ord('<') and i + 1 < len(data) and data[i + 1] != ord('<'):
            # Hex string
            start = i
            i += 1
            while i < len(data) and data[i] != ord('>'):
                i += 1
            i += 1  # Skip '>'
            tokens.append(data[start:i])
        elif c in (ord('['), ord(']'), ord('{'), ord('}')):
            tokens.append(bytes([c]))
            i += 1
        elif c == ord('<') and i + 1 < len(data) and data[i + 1] == ord('<'):
            # Dictionary start
            tokens.append(b'<<')
            i += 2
        elif c == ord('>') and i + 1 < len(data) and data[i + 1] == ord('>'):
            # Dictionary end
            tokens.append(b'>>')
            i += 2
        elif c in b'+-0123456789.':
            # Number
            start = i
            i += 1
            while i < len(data) and data[i] in b'0123456789.+-':
                i += 1
            tokens.append(data[start:i])
        else:
            # Operator or unknown token
            start = i
            i += 1
            while i < len(data) and data[i] not in b' \t\n\r\x00/()<>[]{}%':
                i += 1
            tokens.append(data[start:i])
    return tokens

def unescape_pdf_string(s):
    result = bytearray()
    i = 0
    while i < len(s):
        if s[i] == ord('\\'):
            i += 1
            if i >= len(s):
                break
            c = s[i:i+1]
            if c in b'nrtbf\\()':
                if c == b'n':
                    result.append(ord('\n'))
                elif c == b'r':
                    result.append(ord('\r'))
                elif c == b't':
                    result.append(ord('\t'))
                elif c == b'b':
                    result.append(ord('\b'))
                elif c == b'f':
                    result.append(ord('\f'))
                elif c == b'(':
                    result.append(ord('('))
                elif c == b')':
                    result.append(ord(')'))
                elif c == b'\\':
                    result.append(ord('\\'))
                i += 1
            elif b'0' <= c <= b'7':
                oct_digits = c
                i += 1
                for _ in range(2):
                    if i < len(s) and b'0' <= s[i:i+1] <= b'7':
                        oct_digits += s[i:i+1]
                        i += 1
                    else:
                        break
                result.append(int(oct_digits, 8))
            else:
                result.append(s[i])
                i += 1
        else:
            result.append(s[i])
            i += 1
    return bytes(result)

def extract_text_from_stream(contents):
    text = ''
    tokens = tokenize_stream(contents)
    in_text_object = False
    i = 0

    while i < len(tokens):
        token = tokens[i]
        if token == b'BT':
            in_text_object = True
        elif token == b'ET':
            in_text_object = False
        elif in_text_object:
            if token in [b'Tj', b"'"]:
                if i >= 1:
                    s = tokens[i - 1]
                    if s.startswith(b'(') and s.endswith(b')'):
                        s = s[1:-1]
                        s = unescape_pdf_string(s)
                        text += s.decode('utf-8', 'replace')
            elif token == b'TJ':
                if i >= 1 and tokens[i - 1] == b']':
                    arr_start = i - 1
                    while arr_start >= 0 and tokens[arr_start] != b'[':
                        arr_start -= 1
                    arr = tokens[arr_start + 1:i - 1]
                    for s in arr:
                        if s.startswith(b'(') and s.endswith(b')'):
                            s = s[1:-1]
                            s = unescape_pdf_string(s)
                            text += s.decode('utf-8', 'replace')
                        else:
                            try:
                                kerning = float(s)
                                if kerning < 0:
                                    text += ' '
                            except ValueError:
                                pass
        i += 1

    return text

def extract_object(pdf_data, i):
    match = re.match(rb'\d+\s+\d+\s+obj\n+', pdf_data[i:])
    if not match:
        raise ValueError("Expected object to start with 'n n obj'")
    # print(pdf_data[i+match.start():i+match.end()-1])
    # obj_name = match.group().decode('ascii')
    # if pdf_data[i+match.start():i+match.end()-1] == b'632 0 obj':
    #     print(pdf_data[i:i+100])
    i += match.end()

    if pdf_data[i:i + 2] != b'<<':
        print("Found an object with no dictionary, skipping...")
        match = re.search(rb'endobj\n+', pdf_data[i:])
        if not match:
            raise ValueError("Expected object to end with 'endobj'")
        i += match.end()
        return i, ''
    dictionary, i = parse_dictionary(pdf_data, i)
    i = skip_whitespace(pdf_data, i)
    # if '/fi/' in str(dictionary).lower():
    #     print(dictionary)

    extracted_text = ''
    if pdf_data[i:i + 7] == b'stream\n':
        i += 7
        length = dictionary.get('Length', 0)
        start = i
        end = start + length
        stream_data = pdf_data[start:end]
        if dictionary.get('Filter') == 'FlateDecode':
            try:
                contents = zlib.decompress(stream_data)
            except zlib.error as e:
                contents = b''
        else:
            contents = stream_data
        i = skip_whitespace(pdf_data, end)
        if pdf_data[i:i + 9] != b'endstream':
            raise ValueError("Expected 'endstream' after stream data")
        i += 9

        extracted_text = extract_text_from_stream(contents)

    i = skip_whitespace(pdf_data, i)
    if not pdf_data[i:i + 7] == b'endobj\n':
        raise ValueError("Expected object to end with 'endobj'")
    i += 7

    return i, extracted_text

def extract_text(pdf_path):
    with open(pdf_path, 'rb') as f:
        pdf_data = f.read()

    texts = []

    match = re.search(rb'\d+\s+\d+\s+obj\n+', pdf_data)
    if not match:
        raise ValueError("Expected object to start with 'n n obj'")
    i = match.start()

    while True:
        if pdf_data.startswith(b'%%EOF', i):
            break
        elif pdf_data.startswith(b'startxref\n', i):
            match = re.search(rb'\d+\n', pdf_data[i:])
            if not match:
                raise ValueError("Expected number after 'startxref'")
            i += match.end()
        elif pdf_data.startswith(b'trailer\n', i):
            i += 8
            _, i = parse_dictionary(pdf_data, i)
            i = skip_whitespace(pdf_data, i)
        elif pdf_data.startswith(b'xref\n', i):
            match = re.search(rb'trailer\n', pdf_data[i:])
            if not match:
                raise ValueError("Expected 'trailer' after 'xref'")
            i += match.start()
        else:
            i, extracted_text = extract_object(pdf_data, i)
            if extracted_text:
                texts.append(extracted_text)

    # print('\n'.join(texts))


# Entry point

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: python pdf.py path/to/pdf')
        sys.exit(1)

    pdf_path = sys.argv[1]
    extract_text(pdf_path)
