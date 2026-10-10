#!/usr/bin/env python3
"""Parse Rockchip RSCE (resource.img) container from boot.img second segment,
extract every FDT and print a hardware summary of each."""
import struct
import sys
from pathlib import Path

FDT_MAGIC = b"\xd0\x0d\xfe\xed"


def walk_fdt(data: bytes):
    (magic, totalsize, off_struct, off_strings, off_rsv, version,
     last_ver, boot_cpu, sz_strings, sz_struct) = struct.unpack_from(">10I", data, 0)
    strings = data[off_strings:off_strings + sz_strings]
    pos = off_struct
    stack = []
    nodes = []
    cur = {}
    while True:
        tok = struct.unpack_from(">I", data, pos)[0]
        pos += 4
        if tok == 1:
            end = data.index(b"\0", pos)
            name = data[pos:end].decode(errors="replace")
            pos = (end + 4) & ~3
            stack.append(name)
            cur = {}
        elif tok == 2:
            nodes.append(("/".join(stack), cur))
            stack.pop()
            cur = {}
        elif tok == 3:
            plen, nameoff = struct.unpack_from(">II", data, pos)
            pos += 8
            val = data[pos:pos + plen]
            pos = (pos + plen + 3) & ~3
            pname = strings[nameoff:strings.index(b"\0", nameoff)].decode(errors="replace")
            cur[pname] = val
        elif tok == 4:
            continue
        elif tok == 9:
            break
        else:
            raise ValueError(f"bad token {tok:#x} at {pos:#x}")
    return nodes


def cstr_prop(v: bytes) -> str:
    return ",".join(x.decode(errors="replace") for x in v.split(b"\0") if x)


def summarize(fdt: bytes, label: str, out: Path, idx: int) -> None:
    nodes = walk_fdt(fdt)
    print(f"\n===== {label}: totalsize=0x{len(fdt):x}, {len(nodes)} nodes =====")
    for path, props in nodes:
        comp = cstr_prop(props["compatible"]) if "compatible" in props else ""
        model = cstr_prop(props["model"]) if "model" in props else ""
        status = cstr_prop(props["status"]) if "status" in props else ""
        if path.count("/") <= 1 or comp or model:
            line = f"{path}"
            if model:
                line += f"  model={model}"
            if comp:
                line += f"  compat={comp}"
            if status:
                line += f"  status={status}"
            print(line)
    (out / f"dtb-{idx}.dtb").write_bytes(fdt)


def parse_rsce(blob: bytes, out: Path) -> None:
    assert blob[:4] == b"RSCE", "not RSCE"
    # header: RSCE, u32 ?, u16 ver?, ... count u32 @0x0C
    ver = struct.unpack_from(">I", blob, 8)[0]
    count = struct.unpack_from("<I", blob, 12)[0]
    print(f"RSCE: ver=0x{ver:x} entry_count={count}")
    # entry table: look for 0x20-byte records with tag + offset + size
    for base in (0x10, 0x20, 0x100, 0x200, 0x400, 0x800):
        ok = True
        for i in range(count):
            e = blob[base + i * 0x20: base + i * 0x20 + 0x20]
            tag = e[:4]
            if not all(32 <= c < 127 or c == 0 for c in tag):
                ok = False
                break
        if ok:
            print(f"entry table at 0x{base:x}")
            for i in range(count):
                e = blob[base + i * 0x20: base + i * 0x20 + 0x20]
                tag = e[:4].split(b"\0")[0].decode(errors="replace")
                words = struct.unpack_from("<8I", e, 4) if len(e) >= 36 else ()
                print(f"  [{i}] {tag!r} " + " ".join(f"0x{w:x}" for w in words))
            break
    # extract every FDT inside
    off = 0
    idx = 0
    while True:
        i = blob.find(FDT_MAGIC, off)
        if i < 0:
            break
        totalsize = struct.unpack_from(">I", blob, i + 4)[0]
        if 64 <= totalsize <= 2 << 20:
            fdt = blob[i:i + totalsize]
            try:
                summarize(fdt, f"FDT@0x{i:x}", out, idx)
                idx += 1
            except Exception as exc:  # not a real FDT
                print(f"FDT@0x{i:x}: parse failed ({exc})")
            off = i + totalsize
        else:
            off = i + 4


def main():
    base = Path(sys.argv[1])
    out = base / "parsed"
    out.mkdir(exist_ok=True)
    blob = (base / "parsed" / "second-dtb.bin").read_bytes()
    parse_rsce(blob, out)


if __name__ == "__main__":
    main()
