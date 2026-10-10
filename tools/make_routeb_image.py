#!/usr/bin/env python3
"""Assemble a full GPT disk image for AI3399-C route B (vendor boot chain).

Layout (512-byte sectors), mirroring vendor/parameter-armbian.txt:
  loader area : MiniLoaderAll at sector 64 (0x40)
  uboot       : 0x4000  0x2000 sectors
  trust       : 0x6000  0x2000
  misc        : 0x8000  0x2000
  dtb         : 0xA000  0x2000
  dtbo        : 0xC000  0x2000
  vbmeta      : 0xE000  0x800
  boot        : 0xE800  0x16000   (Android boot.img: vendor kernel + RSCE)
  rootfs      : 0x24800 grow      (Armbian ext4)

Usage:
  make_routeb_image.py --loader MiniLoaderAll.bin --uboot uboot.img \
      --trust trust.img --boot boot-armbian-vendor.img \
      --rootfs rootfs.ext4 --output Armbian_vendor419_AI3399C.img
"""
import argparse
import os
import struct
import zlib

SECTOR = 512
PART_TYPE = bytes.fromhex("af3dc60f838472428e793d69d8477de4")  # Linux fs (LE)


def crc32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def build_gpt(disk_sectors: int, parts):
    """parts: list of (name, first_lba, last_lba). Returns (head, tail):
    head = protective MBR + primary header + entry table (LBA 0..33),
    tail = backup entry table + backup header (33 sectors at disk end)."""
    n_ent = 128
    ent_sectors = n_ent * 128 // SECTOR          # 32
    entries = bytearray(128 * n_ent)
    for i, (name, first, last) in enumerate(parts):
        e = entries[i * 128:(i + 1) * 128]
        e[0:16] = PART_TYPE
        e[16:32] = os.urandom(16)          # unique GUID
        struct.pack_into("<QQQ", e, 32, first, last, 0)
        nm = name.encode("utf-16-le")[:72]
        e[56:56 + len(nm)] = nm
    entries_crc = crc32(bytes(entries))
    disk_guid = os.urandom(16)

    first_usable = 2 + ent_sectors
    last_usable = disk_sectors - 2 - ent_sectors

    def mk_hdr(current_lba, backup_lba, entries_lba):
        h = bytearray(92)
        h[0:8] = b"EFI PART"
        struct.pack_into("<I", h, 8, 0x00010000)     # revision
        struct.pack_into("<I", h, 12, 92)            # header size
        h[16:20] = b"\0\0\0\0"                       # crc placeholder
        struct.pack_into("<QQ", h, 24, current_lba, backup_lba)
        struct.pack_into("<QQ", h, 40, first_usable, last_usable)
        h[56:72] = disk_guid
        struct.pack_into("<Q", h, 72, entries_lba)
        struct.pack_into("<III", h, 80, n_ent, 128, entries_crc)
        struct.pack_into("<I", h, 16, crc32(bytes(h)))
        return bytes(h)

    primary_hdr = mk_hdr(1, disk_sectors - 1, 2)
    backup_hdr = mk_hdr(disk_sectors - 1, 1, disk_sectors - 1 - ent_sectors)

    mbr = bytearray(SECTOR)
    mbr[446 + 4] = 0xEE                    # protective GPT type
    struct.pack_into("<II", mbr, 446 + 8, 1, min(disk_sectors - 1, 0xFFFFFFFF))
    mbr[510:512] = b"\x55\xaa"

    head = bytes(mbr) + primary_hdr + bytes(entries)
    tail = bytes(entries) + backup_hdr
    return head, tail


def copy_into(out, off, path):
    size = 0
    with open(path, "rb") as f, open(out, "r+b") as o:
        o.seek(off)
        while True:
            chunk = f.read(16 << 20)
            if not chunk:
                break
            o.write(chunk)
            size += len(chunk)
    print(f"  {path} -> offset 0x{off:x} ({size} bytes)")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--loader", required=True)
    p.add_argument("--uboot", required=True)
    p.add_argument("--trust", required=True)
    p.add_argument("--boot", required=True)
    p.add_argument("--rootfs", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()

    rootfs_size = os.path.getsize(a.rootfs)
    rootfs_sectors = (rootfs_size + SECTOR - 1) // SECTOR
    last = 0x24800 + rootfs_sectors - 1
    disk_sectors = last + 1 + 33 + 32  # room for backup GPT

    parts = [
        ("uboot", 0x4000, 0x5FFF),
        ("trust", 0x6000, 0x7FFF),
        ("misc", 0x8000, 0x9FFF),
        ("dtb", 0xA000, 0xBFFF),
        ("dtbo", 0xC000, 0xDFFF),
        ("vbmeta", 0xE000, 0xE7FF),
        ("boot", 0xE800, 0x247FF),
        ("rootfs", 0x24800, last),
    ]
    head, tail = build_gpt(disk_sectors, parts)

    print(f"creating {a.output} ({disk_sectors * SECTOR} bytes)")
    with open(a.output, "wb") as f:
        f.truncate(disk_sectors * SECTOR)
    with open(a.output, "r+b") as f:
        f.write(head)
        f.seek((disk_sectors - 33) * SECTOR)
        f.write(tail)

    copy_into(a.output, 64 * SECTOR, a.loader)
    copy_into(a.output, 0x4000 * SECTOR, a.uboot)
    copy_into(a.output, 0x6000 * SECTOR, a.trust)
    copy_into(a.output, 0xE800 * SECTOR, a.boot)
    copy_into(a.output, 0x24800 * SECTOR, a.rootfs)
    print("done")


if __name__ == "__main__":
    main()
