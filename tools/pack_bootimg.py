#!/usr/bin/env python3
"""Pack an Android boot.img (header v0/v2) for the RK3399 vendor U-Boot chain.

The vendor U-Boot boot_android loads kernel/ramdisk/second from the "boot"
partition.  On AI3399-C the "second" segment is a Rockchip RSCE container
carrying the DTBs (see tools/extract_rsce.py).  This tool rebuilds a boot.img
from:

  --kernel   kernel Image (e.g. vendor 4.19.172 Image)
  --ramdisk  initramfs cpio(.gz) (e.g. Armbian initrd)
  --second   RSCE blob (e.g. stock boot.img second segment)
  --template stock boot.img (keeps load addresses / os_version fields)
  --cmdline  appended kernel cmdline (root=... etc.)
  --output   resulting boot.img

Layout: header | kernel (page aligned) | ramdisk (page aligned) |
        second (page aligned) | recovery_dtbo (page aligned, v2 only).
"""
import argparse
import struct


def align(x: int, page: int) -> int:
    return (x + page - 1) // page * page


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--template", required=True, help="stock boot.img to copy header fields from")
    p.add_argument("--kernel", required=True)
    p.add_argument("--ramdisk", required=True)
    p.add_argument("--second", default=None)
    p.add_argument("--cmdline", default="")
    p.add_argument("--page-size", type=int, default=None)
    p.add_argument("--header-version", type=int, default=None)
    p.add_argument("--output", required=True)
    return p.parse_args()


def main():
    a = parse_args()
    tmpl = open(a.template, "rb").read(4096)
    assert tmpl[:8] == b"ANDROID!", "template is not an Android boot image"

    (t_ksize, kaddr, t_rsize, raddr, t_ssize, saddr, tags_addr,
     page_size, dt_size, unused) = struct.unpack_from("<10I", tmpl, 8)
    name = tmpl[48:64]
    t_cmdline = tmpl[64:576].split(b"\0", 1)[0].decode(errors="replace")
    t_id = tmpl[576:608]
    extra_cmdline = tmpl[608:1632]

    hdr_ver = 0
    if len(tmpl) >= 1652:
        hdr_ver = struct.unpack_from("<I", tmpl, 1632 + 12)[0]  # header_size@1644 then ver?
        # header version lives at offset 1632-4? be explicit: v1: recovery_dtbo_size@1632,
        # recovery_dtbo_offset@1636(u64), header_size@1644, v2: total_size@1648.
        # The standard header_version field is at 40? No: it is at 1632-4+... use spec:
        # boot_img_hdr_v1 ends with header_version u32 at offset 1628.
        hdr_ver = struct.unpack_from("<I", tmpl, 1628)[0]

    if a.page_size:
        page_size = a.page_size
    if a.header_version is not None:
        hdr_ver = a.header_version

    kernel = open(a.kernel, "rb").read()
    ramdisk = open(a.ramdisk, "rb").read()
    second = open(a.second, "rb").read() if a.second else b""

    cmdline = a.cmdline.encode()
    full_cmdline = (t_cmdline + " " + a.cmdline).encode() if a.cmdline else t_cmdline.encode()
    if len(full_cmdline) > 511:
        # overflow into extra_cmdline (1024 bytes) as the spec allows
        main_cmd = full_cmdline[:511]
        extra = full_cmdline[511:511 + 1024]
    else:
        main_cmd = full_cmdline
        extra = b""

    hdr = bytearray(1632)
    hdr[0:8] = b"ANDROID!"
    struct.pack_into("<10I", hdr, 8, len(kernel), kaddr, len(ramdisk), raddr,
                     len(second), saddr, tags_addr, page_size, 0, 0)
    hdr[48:64] = name
    hdr[64:64 + len(main_cmd)] = main_cmd
    hdr[576:608] = t_id
    hdr[608:608 + len(extra)] = extra

    if hdr_ver >= 1:
        hdr += struct.pack("<I", 0)              # recovery_dtbo_size
        hdr += struct.pack("<Q", 0)              # recovery_dtbo_offset (filled later)
        hdr += struct.pack("<I", 1648)           # header_size (v1)
    if hdr_ver >= 2:
        total = align(len(hdr) + 4, page_size) + align(len(kernel), page_size) \
            + align(len(ramdisk), page_size) + align(len(second), page_size)
        hdr += struct.pack("<I", total)          # total_size
        struct.pack_into("<Q", hdr, 1636, align(len(hdr), page_size)
                         + align(len(kernel), page_size) + align(len(ramdisk), page_size)
                         + align(len(second), page_size))
        struct.pack_into("<I", hdr, 1644, 1652)  # header_size (v2)

    out = bytearray()
    out += hdr
    out += b"\0" * (align(len(out), page_size) - len(out))
    out += kernel
    out += b"\0" * (align(len(out), page_size) - len(out))
    out += ramdisk
    out += b"\0" * (align(len(out), page_size) - len(out))
    out += second
    out += b"\0" * (align(len(out), page_size) - len(out))

    with open(a.output, "wb") as f:
        f.write(out)
    print(f"boot.img written: {a.output}")
    print(f"  header_version={hdr_ver} page_size={page_size}")
    print(f"  kernel=0x{len(kernel):x} ramdisk=0x{len(ramdisk):x} second=0x{len(second):x}")
    print(f"  cmdline: {(main_cmd + extra).decode(errors='replace')[:200]}")


if __name__ == "__main__":
    main()
