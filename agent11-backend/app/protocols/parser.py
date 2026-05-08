from __future__ import annotations

import binascii
from dataclasses import dataclass

from app.protocols.spec import ProtocolSpec, ProtocolFieldSpec


def _hex_to_bytes(raw_hex: str) -> bytes:
    s = raw_hex.strip().lower()
    if s.startswith("0x"):
        s = s[2:]
    s = "".join(s.split())
    if len(s) % 2 == 1:
        s = "0" + s
    try:
        return binascii.unhexlify(s)
    except (binascii.Error, ValueError) as e:
        raise ValueError("raw_data must be a hex string") from e


def _decode_field(buf: bytes, f: ProtocolFieldSpec):
    start = f.offset
    end = f.offset + f.length
    if end > len(buf):
        raise ValueError(f"field '{f.name}' out of range: need {end} bytes, got {len(buf)}")
    b = buf[start:end]

    t = f.type.lower()
    endian = f.endian.lower()
    if endian not in ("big", "little"):
        raise ValueError(f"field '{f.name}' has invalid endian: {f.endian}")

    if t in ("uint", "int"):
        val = int.from_bytes(b, byteorder=endian, signed=(t == "int"))
        scaled = val * (f.scale or 1.0)
        return scaled
    if t == "hex":
        return b.hex()
    if t == "ascii":
        return b.decode("ascii", errors="replace").rstrip("\x00")

    raise ValueError(f"field '{f.name}' has unsupported type: {f.type}")


def parse_raw_data(raw_data_hex: str, spec: ProtocolSpec) -> dict:
    buf = _hex_to_bytes(raw_data_hex)
    out: dict[str, object] = {"_bytes_len": len(buf)}
    for f in spec.fields:
        out[f.name] = _decode_field(buf, f)
    return out

