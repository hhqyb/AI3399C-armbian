#!/usr/bin/env python3
"""Inspect Rockchip Android boot.img, raw DTB and dtbo.img from AI3399-C."""
import struct
import sys
from pathlib import Path


def parse_boot_img(path: Path, out: Path) -> None:
    data = path.read_bytes()
    if data[:8] != b"ANDROID!":
        print(f"{path.name}: not an Android boot image")
        return
    (kernel_size, kernel_addr, ramdisk_size, ramdisk_addr, second_size,
     second_addr, tags_addr, page_size, dt_size, unused) = struct.unpack_from("<10I", data, 8)
    name = data[48:64].split(b"\0", 1)[0].decode(errors="replace")
    cmdline = data[64:576].split(b"\0", 1)[0].decode(errors="replace")
    hdr_ver = struct.unpack_from("<I", data, 40 + 8 * 4 + 8 + 16 + 512 + 0)[0] if len(data) > 1632 else 0
    # header version lives at offset 40 for v0... actually at +40..; try known offset 1632? keep simple:
    print(f"== boot.img {path.name}: page_size={page_size} kernel=0x{kernel_size:x} "
          f"ramdisk=0x{ramdisk_size:x} second=0x{second_size:x} dt_size=0x{dt_size:x}")
    print(f"   name={name!r}")
    print(f"   cmdline={cmdline[:300]}")
    koff = page_size
    kernel = data[koff:koff + kernel_size]
    (out / "kernel-extracted.bin").write_bytes(kernel)
    idx = kernel.find(b"Linux version ")
    if idx >= 0:
        print("   " + kernel[idx:idx + 120].decode(errors="replace"))
    roff = koff + ((kernel_size + page_size - 1) // page_size) * page_size
    if ramdisk_size:
        (out / "ramdisk-extracted.cpio.gz").write_bytes(data[roff:roff + ramdisk_size])
    # recovery_dtbo for header v2 sits after ramdisk/second
    print(f"   kernel saved: {out / 'kernel-extracted.bin'}")


def walk_fdt(data: bytes):
    (magic, totalsize, off_struct, off_strings, off_rsv, version,
     last_ver, boot_cpu, sz_strings, sz_struct) = struct.unpack_from(">10I", data, 0)
    assert magic == 0xD00DFEED, f"bad FDT magic {magic:#x}"
    strings = data[off_strings:off_strings + sz_strings]
    pos = off_struct
    path = []
    out_nodes = []
    cur = {}
    while True:
        tok = struct.unpack_from(">I", data, pos)[0]
        pos += 4
        if tok == 1:  # BEGIN_NODE
            end = data.index(b"\0", pos)
            name = data[pos:end].decode(errors="replace")
            pos = (end + 4) & ~3
            path.append(name or "/")
            cur = {}
        elif tok == 2:  # END_NODE
            out_nodes.append(("/".join(path), cur))
            path.pop()
            cur = {}
        elif tok == 3:  # PROP
            plen, nameoff = struct.unpack_from(">II", data, pos)
            pos += 8
            val = data[pos:pos + plen]
            pos = (pos + plen + 3) & ~3
            pname = strings[nameoff:strings.index(b"\0", nameoff)].decode(errors="replace")
            cur[pname] = val
        elif tok == 4:  # NOP
            continue
        elif tok == 9:  # END
            break
        else:
            raise ValueError(f"bad token {tok} at {pos:#x}")
    return out_nodes


def fmt_prop(name: str, val: bytes) -> str:
    if name in ("compatible", "model", "status", "phy-mode", "phy-handle",
                "clock-names", "reg-names", "serial0", "serial1", "serial2",
                "i2c-names", "spi-names", "sound-dai", "rockchip,hdmi",
                "rockchip,lvds", "panel-name", "backlight"):
        try:
            s = val.split(b"\0")
            txt = ",".join(x.decode(errors="replace") for x in s if x)
            return txt
        except Exception:
            pass
    if len(val) <= 32 and len(val) % 4 == 0 and len(val) > 0:
        words = struct.unpack(f">{len(val)//4}I", val)
        return " ".join(f"{w:#x}" for w in words)
    return f"<{len(val)} bytes>"


def dump_dtb(path: Path, full: bool = False) -> None:
    data = path.read_bytes()
    # some vendor dtb partitions pad with 0x00 or have 4-byte length prefix
    off = data.find(b"\xd0\x0d\xfe\xed")
    if off < 0:
        print(f"{path.name}: no FDT found")
        return
    total = struct.unpack_from(">I", data, off + 4)[0]
    fdt = data[off:off + total]
    print(f"== {path.name}: FDT at 0x{off:x}, totalsize=0x{total:x}")
    nodes = walk_fdt(fdt)
    print(f"   nodes: {len(nodes)}")
    for p, props in nodes:
        interesting = {k: v for k, v in props.items()
                       if k in ("compatible", "model", "status")}
        if p == "/" or interesting:
            line = f"   {p or '/'}"
            for k, v in interesting.items():
                line += f"  {k}={fmt_prop(k, v)}"
            print(line)
        if full:
            for k, v in props.items():
                if k not in interesting:
                    print(f"      .{k} = {fmt_prop(k, v)}")


def parse_dtbo(path: Path, out: Path) -> None:
    data = path.read_bytes()
    if struct.unpack_from(">I", data, 0)[0] != 0xD7B7AB1E:
        print(f"{path.name}: no dt_table magic")
        return
    total, hdr, entry, cnt, ver = struct.unpack_from(">5I", data, 4)
    print(f"== dtbo.img: entries={cnt} entry_size={entry} total=0x{total:x} ver={ver}")
    out.mkdir(parents=True, exist_ok=True)
    for i in range(cnt):
        eoff = hdr + i * entry
        dt_off, dt_size, id_, rev, custom = struct.unpack_from(">5I", data, eoff)
        dtb = data[dt_off:dt_off + dt_size]
        (out / f"dtbo-{i:02}-id{id_:x}.dtb").write_bytes(dtb)
        total_sz, = struct.unpack_from(">I", dtb, 4)
        strings_off = struct.unpack_from(">I", dtb, 12)[0]
        strings = dtb[strings_off:]
        model = b""
        # quick model scan
        idx = dtb.find(b"rockchip,", 0)
        comp = dtb[idx:idx + 200].split(b"\0")[0] if idx >= 0 else b""
        print(f"   [{i}] off=0x{dt_off:x} size=0x{dt_size:x} id=0x{id_:x} rev=0x{rev:x} "
              f"hint={comp.decode(errors='replace')}")
    print(f"   dtbs saved under {out}")


def main():
    base = Path(sys.argv[1])
    out = base / "parsed"
    out.mkdir(exist_ok=True)
    for name in ("live-boot.img", "Image/boot.img"):
        p = base / name
        if p.exists():
            parse_boot_img(p, out)
    for name in ("live-dtb.img", "Image/dtb.img"):
        p = base / name
        if p.exists():
            dump_dtb(p)
    for name in ("live-dtbo.img", "Image/dtbo.img"):
        p = base / name
        if p.exists():
            parse_dtbo(p, out / "dtbo")


if __name__ == "__main__":
    main()
