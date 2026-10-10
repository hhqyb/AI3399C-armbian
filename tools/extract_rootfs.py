#!/usr/bin/env python3
"""Extract the rootfs partition (last GPT entry) from a compressed Armbian image."""
import lzma
import struct
import sys
import shutil


def main(xz_path: str, img_path: str, out_path: str) -> None:
    print("decompressing...")
    with lzma.open(xz_path, "rb") as fi, open(img_path, "wb") as fo:
        shutil.copyfileobj(fi, fo, 16 << 20)

    with open(img_path, "rb") as f:
        gpt = f.read(92)
        f.seek(0)
        mbr = f.read(512)
        parts = []
        if gpt[:8] == b"EFI PART":
            elba = struct.unpack_from("<Q", gpt, 72)[0]
            num = struct.unpack_from("<I", gpt, 80)[0]
            esz = struct.unpack_from("<I", gpt, 84)[0]
            f.seek(elba * 512)
            for _ in range(num):
                e = f.read(esz)
                if e[:16] == b"\0" * 16:
                    continue
                name = e[56:128].decode("utf-16-le").rstrip("\0")
                first, last = struct.unpack_from("<QQ", e, 32)
                parts.append((name, first, last))
        else:
            assert mbr[510:512] == b"\x55\xaa", "neither GPT nor MBR"
            for i in range(4):
                e = mbr[446 + i * 16:446 + (i + 1) * 16]
                if e[4] == 0:
                    continue
                start, count = struct.unpack_from("<II", e, 8)
                parts.append((f"mbr{i + 1}", start, start + count - 1))
        for name, first, last in parts:
            print(f"  {name:12s} LBA {first:#x}-{last:#x}  {(last - first + 1) * 512 / 1048576:.0f} MiB")

        name, first, last = parts[-1]
        print(f"extracting rootfs partition '{name}' -> {out_path}")
        f.seek(first * 512)
        remaining = (last - first + 1) * 512
        with open(out_path, "wb") as o:
            while remaining:
                chunk = f.read(min(remaining, 16 << 20))
                if not chunk:
                    raise SystemExit("short read")
                o.write(chunk)
                remaining -= len(chunk)
    print("done")


if __name__ == "__main__":
    main(*sys.argv[1:4])
