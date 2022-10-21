from io import BytesIO
from typing import BinaryIO, TypeVar


def parse_int(f: BytesIO | BinaryIO, length: int) -> int:
    return int.from_bytes(f.read(length), 'big')


def parse_cp_index(f: BinaryIO):
    return parse_int(f, 2) - 1


def read_until(f: BytesIO, delim: bytes):
    assert len(delim) == 1
    res = b''
    while (b := f.read(1)) != delim:
        res += b
    return res


T = TypeVar('T')

