from dataclasses import dataclass
import struct
import warnings

from typing import Any, Tuple

from .constants import TIFF_TAGS, HEADER_OFFSET

@dataclass
class TagType:
    """
    Represents the type of a TIFF tag.  Also responsible for reading the tag since this is dependent on the tag's type.
    """
    format: str
    size: int


TAG_TYPES = {
    1: TagType(format='B', size=1), # TIFFByte
    2: TagType(format='c', size=1), # TIFFascii
    3: TagType(format='H', size=2), # TIFFshort
    4: TagType(format='L', size=4), # TIFFlong
    5: TagType(format='f', size=4), # TIFFrational
    7: TagType(format='B', size=1), # undefined
    12: TagType(format='d', size=8), # TIFFdouble
    16: TagType(format='Q', size=8), # TIFFlong8
}


@dataclass
class Tag:
    code: int
    name: str
    tag_type: TagType
    count: int
    length: int
    value: Tuple[Any]

    def __getitem__(self, key):
        return self.value[key]

    def __len__(self):
        return self.count


    @classmethod
    async def read(cls, reader):
        # 0-2 bytes of tag are tag name
        code = await reader.read(2, cast_to_int=True)
        if code not in TIFF_TAGS:
            warnings.warn(f"TIFF TAG {code} is not supported.")
            reader.incr(10)
            return None
        name = TIFF_TAGS[code]
        # 2-4 bytes are field type
        field_type = TAG_TYPES[(await reader.read(2, cast_to_int=True))]
        # 4-8 bytes are number of values
        count = await reader.read(4, cast_to_int=True)
        length = field_type.size * count
        if length <= 4:
            value = struct.unpack(f"{reader._endian}{count}{field_type.format}", (await reader.read(length)))
            reader.incr(4 - length)
        else:
            value_offset = await reader.read(4, cast_to_int=True)
            end_of_tag = reader.tell()
            if value_offset + length > HEADER_OFFSET:
                data = await reader.range_request(value_offset, length - 1)
            else:
                reader.seek(value_offset)
                data = await reader.read(length)
            value = struct.unpack(f"{reader._endian}{count}{field_type.format}", data)
            reader.seek(end_of_tag)
        value = value[0] if count == 1 else value
        tag = Tag(
            code=code,
            name=name,
            tag_type=field_type,
            count=count,
            length=length,
            value=value
        )
        return tag