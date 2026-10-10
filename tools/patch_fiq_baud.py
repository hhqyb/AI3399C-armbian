#!/usr/bin/env python3
"""Patch the fiq-debugger baud rate inside the RSCE DTB blob.

The AI3399-C vendor DTB has /fiq-debugger { rockchip,baudrate = <0>; } which
makes the debugger use 1500000 baud (invisible to a PC 16550 UART).
This tool rewrites the property value to the requested baud (e.g. 115200)
in every FDT contained in the RSCE image.
"""
import struct
import sys


def patch_fdt(data: bytearray, base: int, new_baud: int) -> int:
    (magic, totalsize, off_struct, off_strings, off_rsv, version,
     last_ver, boot_cpu, sz_strings, sz_struct) = struct.unpack_from(">10I", data, base)
    strings = data[base + off_strings:base + off_strings + sz_strings]
    pos = base + off_struct
    path = []
    patched = 0
    while True:
        tok = struct.unpack_from(">I", data, pos)[0]
        if tok == 1:  # BEGIN_NODE
            end = data.index(b"\0", pos + 4)
            name = data[pos + 4:end].decode(errors="replace")
            pos = (end + 4) & ~3
            path.append(name)
        elif tok == 2:  # END_NODE
            path.pop()
            pos += 4
        elif tok == 3:  # PROP
            plen, nameoff = struct.unpack_from(">II", data, pos + 4)
            pname = strings[nameoff:strings.index(b"\0", nameoff)].decode(errors="replace")
            val_off = pos + 12
            if path and path[-1] == "fiq-debugger" and pname == "rockchip,baudrate":
                old = struct.unpack_from(">I", data, val_off)[0] if plen >= 4 else 0
                struct.pack_into(">I", data, val_off, new_baud)
                print(f"    fiq-debugger rockchip,baudrate: {old} -> {new_baud} (at 0x{val_off:x})")
                patched += 1
            pos = (val_off + plen + 3) & ~3
        elif tok == 4:
            pos += 4
        elif tok == 9:
            break
        else:
            raise ValueError(f"bad token {tok:#x} at {pos:#x}")
    return patched


def main(rsce_path: str, baud: int, out_path: str) -> None:
    data = bytearray(open(rsce_path, "rb").read())
    assert data[:4] == b"RSCE", "not an RSCE blob"
    off = 0
    n = 0
    while True:
        i = data.find(b"\xd0\x0d\xfe\xed", off)
        if i < 0:
            break
        totalsize = struct.unpack_from(">I", data, i + 4)[0]
        if 64 <= totalsize <= 2 << 20:
            print(f"  FDT@0x{i:x} (0x{totalsize:x} bytes):")
            n += patch_fdt(data, i, baud)
            off = i + totalsize
        else:
            off = i + 4
    open(out_path, "wb").write(data)
    print(f"patched {n} properties; wrote {out_path}")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), sys.argv[3])
