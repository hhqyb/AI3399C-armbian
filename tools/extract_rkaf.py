#!/usr/bin/env python3
"""Extract Rockchip RKAF update image (port of afptool-rs unpack logic).

Header layout (2048 bytes):
  magic[4]="RKAF", length u32@4, model[34]@8, id[30]@42, manufacturer[56]@72,
  unknown1 u32@128, version u32@132, num_parts u32@136, parts[16]@140 (112 B each):
  name[32], full_path[60], flash_size u32@92, part_offset u32@96,
  flash_offset u32@100, padded_size u32@104, part_byte_count u32@108.
"""
import struct
import sys
from pathlib import Path

SECTOR = 2048
HDR = 2048
PART_SZ = 112
MAGIC = b"RKAF"


def cstr(b: bytes) -> str:
    return b.split(b"\x00", 1)[0].decode("utf-8", "replace")


def recover_true_size(stored: int, available: int) -> int:
    if available <= stored:
        return stored
    return stored + (((available - stored) >> 32) << 32)


def main(img_path: str, out_dir: str) -> None:
    src = Path(img_path)
    out = Path(out_dir)
    (out / "Image").mkdir(parents=True, exist_ok=True)
    filesize = src.stat().st_size

    with open(src, "rb") as fp:
        head = fp.read(HDR)
        if head[:4] != MAGIC:
            sys.exit("not an RKAF image")
        length = struct.unpack_from("<I", head, 4)[0]
        model = cstr(head[8:42])
        ident = cstr(head[42:72])
        manufacturer = cstr(head[72:128])
        version = struct.unpack_from("<I", head, 132)[0]
        num_parts = struct.unpack_from("<I", head, 136)[0]
        print(f"model={model!r} id={ident!r} manufacturer={manufacturer!r}")
        print(f"length=0x{length:x} version=0x{version:x} num_parts={num_parts} filesize={filesize}")

        parts = []
        for i in range(num_parts):
            raw = head[140 + i * PART_SZ: 140 + (i + 1) * PART_SZ]
            name = cstr(raw[0:32])
            full_path = cstr(raw[32:92])
            flash_size, part_offset, flash_offset, padded_size, byte_count = \
                struct.unpack_from("<5I", raw, 92)
            parts.append(dict(name=name, path=full_path, flash_size=flash_size,
                              off=part_offset, flash_off=flash_offset,
                              padded=padded_size, count=byte_count))

        container_end = filesize - 4  # trailing CRC32

        # recover layout in package order (u32 offset fields wrap at 4 GiB)
        layout = []
        prev_end = 0
        known = []
        for p in parts:
            raw_off = p["off"]
            if raw_off == 0:
                layout.append((0, p["count"]))
                continue
            hit = next((k for k in known
                        if k[0] == raw_off and k[1] == p["path"]), None)
            if hit:
                layout.append((hit[2], hit[3]))
                continue
            padded_bytes = p["padded"] * SECTOR
            true_count = recover_true_size(p["count"], padded_bytes) if padded_bytes else p["count"]
            alloc = padded_bytes or (true_count + SECTOR - 1) // SECTOR * SECTOR
            off = raw_off
            if off < prev_end:
                wraps = (prev_end - off + (1 << 32) - 1) >> 32
                off += wraps << 32
            assert off + true_count <= container_end, f"range overflow for {p['name']}"
            layout.append((off, true_count))
            known.append((raw_off, p["path"], off, true_count))
            prev_end = off + alloc

        meta = ["# name,path,flash_size,flash_offset,part_offset,padded_size,byte_count,real_offset,real_size"]
        for i, p in enumerate(parts):
            off, count = layout[i]
            meta.append(f"{p['name']},{p['path']},0x{p['flash_size']:x},0x{p['flash_off']:x},"
                        f"0x{p['off']:x},0x{p['padded']:x},0x{p['count']:x},0x{off:x},0x{count:x}")
            if p["path"] in ("SELF", "RESERVED") or not p["path"]:
                continue
            # PARM wrapper for "parameter": magic[4] + len u32 + content + crc u32
            data_off, data_len = off, count
            if p["name"] == "parameter" and count >= 12:
                fp.seek(off)
                h8 = fp.read(8)
                content_len = struct.unpack_from("<I", h8, 4)[0]
                data_off, data_len = off + 8, content_len
            dst = out / p["path"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            fp.seek(data_off)
            remaining = data_len
            with open(dst, "wb") as fo:
                while remaining:
                    chunk = fp.read(min(remaining, 4 << 20))
                    if not chunk:
                        sys.exit(f"short read at 0x{data_off:x}")
                    fo.write(chunk)
                    remaining -= len(chunk)
            print(f"0x{data_off:08x} 0x{data_len:08x} -> {p['path']}  ({p['name']})")

        (out / "partition-metadata.txt").write_text("\n".join(meta) + "\n", encoding="utf-8")
        print("partition-metadata.txt written")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
