#!/usr/bin/env python3
"""Build a gadget-console initramfs for AI3399-C debugging.

Contains: /init (shell), /bin/busybox (static), /dev/sh dirs.
The init script sets up a USB ACM serial + RNDIS gadget over the board's
Type-C port, opens a shell on the ACM serial and a telnetd on the RNDIS
interface, then tries to mount and switch into the rootfs.  On any failure
it stays alive so the console/telnet remain usable for debugging.
"""
import gzip
import io
import stat
import struct
import sys

INIT_SCRIPT = r"""#!/bin/busybox sh
BB=/bin/busybox
$BB mount -t proc proc /proc
$BB mount -t sysfs sysfs /sys
$BB mount -t devtmpfs devtmpfs /dev 2>/dev/null
$BB mkdir -p /dev/pts /tmp /newroot /sys/kernel/config
$BB mount -t configfs configfs /sys/kernel/config 2>/dev/null

log() {
    echo "$@"
    echo "initramfs: $@" > /dev/kmsg 2>/dev/null
    echo "$@" > /dev/ttyGS0 2>/dev/null
    echo "$@" > /dev/tty1 2>/dev/null
}

log "AI3399C gadget initramfs alive"

# ---- USB gadget (ACM serial + RNDIS), one gadget per UDC ----
i=0
for udc in $($BB ls /sys/class/udc 2>/dev/null); do
    i=$((i+1))
    gd=/sys/kernel/config/usb_gadget/g$i
    $BB mkdir -p "$gd" 2>/dev/null
    cd "$gd" || continue
    echo 0x1d6b > idVendor
    echo 0x0104 > idProduct
    echo 0x0200 > bcdUSB
    $BB mkdir -p strings/0x409
    echo AI3399C$i > strings/0x409/serialnumber
    echo LCS > strings/0x409/manufacturer
    echo gadget-console > strings/0x409/product
    $BB mkdir -p functions/acm.usb0
    $BB mkdir -p functions/rndis.usb0 2>/dev/null
    $BB mkdir -p configs/c.1/strings/0x409
    echo conf > configs/c.1/strings/0x409/configuration
    $BB ln -s functions/acm.usb0 configs/c.1/ 2>/dev/null
    $BB ln -s functions/rndis.usb0 configs/c.1/ 2>/dev/null
    echo "$udc" > UDC
    log "gadget g$i bound to UDC $udc"
done

# ---- interactive shell on ACM serial ----
$BB setsid $BB sh -c '$BB sh -i < /dev/ttyGS0 > /dev/ttyGS0 2>&1' &

# ---- network on rndis ----
$BB sleep 2
for n in usb0 usb1 rndis0 rndis1; do
    $BB ifconfig $n 192.168.77.1 netmask 255.255.255.0 up 2>/dev/null
done
$BB telnetd -l /bin/busybox -p 23 2>/dev/null &
log "telnetd on 192.168.77.1:23, ACM shell on ttyGS0"

# ---- locate rootfs partition by PARTNAME ----
rootdev=""
for u in /sys/class/block/*/uevent; do
    if $BB grep -q 'PARTNAME=rootfs' "$u" 2>/dev/null; then
        d=$($BB grep '^DEVNAME=' "$u" | $BB cut -d= -f2)
        rootdev="/dev/$d"
        log "rootfs partition found: $rootdev"
    fi
done

# fallback: first ext4 filesystem that has /sbin/init
trydevs="$rootdev /dev/mmcblk1p8 /dev/mmcblk2p8 /dev/mmcblk0p8 /dev/mmcblk1p2 /dev/mmcblk2p15"
if [ -z "$rootdev" ]; then
    for d in $trydevs; do
        [ -b "$d" ] || continue
        if $BB mount -t ext4 -o ro "$d" /newroot 2>/dev/null; then
            if [ -x /newroot/sbin/init ] || [ -x /newroot/usr/sbin/init ]; then
                rootdev="$d"
                $BB umount /newroot
                log "rootfs guessed: $d"
                break
            fi
            $BB umount /newroot
        fi
    done
fi

if [ -n "$rootdev" ]; then
    log "mounting $rootdev on /newroot (rw)"
    if $BB mount -t ext4 -o rw "$rootdev" /newroot 2>/dev/null; then
        $BB mount --move /proc /newroot/proc 2>/dev/null
        $BB mount --move /sys /newroot/sys 2>/dev/null
        $BB mount --move /dev /newroot/dev 2>/dev/null
        log "switch_root -> /sbin/init"
        exec $BB switch_root /newroot /sbin/init
        log "switch_root failed"
    else
        log "mount rw failed on $rootdev"
    fi
else
    log "NO rootfs partition found"
fi

log "INITRAMFS SHELL REMAINS ACTIVE (debug mode)"
exec $BB sh
"""

CPPIO_TRAILER = b"TRAILER!!!"


def cpio_entry(name: str, data: bytes, mode: int, ino: int) -> bytes:
    name_b = name.encode() + b"\0"
    hdr = b"070701"
    fields = [ino, mode, 0, 0, 1, 0, len(data), 0, 0, 0, 0, len(name_b), 0]
    hdr += b"".join(b"%08X" % f for f in fields)
    out = hdr + name_b
    out += b"\0" * ((4 - len(out) % 4) % 4)
    out += data
    out += b"\0" * ((4 - len(data) % 4) % 4)
    return out


def main(busybox_path: str, out_path: str) -> None:
    bb = open(busybox_path, "rb").read()
    init = INIT_SCRIPT.encode()
    buf = io.BytesIO()
    ino = 1
    # dirs: /bin /dev /proc /sys /tmp /newroot
    for d in ["bin", "dev", "proc", "sys", "tmp", "newroot"]:
        buf.write(cpio_entry(d, b"", stat.S_IFDIR | 0o755, ino)); ino += 1
    buf.write(cpio_entry("init", init, stat.S_IFREG | 0o755, ino)); ino += 1
    buf.write(cpio_entry("bin/busybox", bb, stat.S_IFREG | 0o755, ino)); ino += 1
    buf.write(cpio_entry(CPPIO_TRAILER.decode(), b"", 0, ino))
    raw = buf.getvalue()
    gz = gzip.compress(raw, 9)
    open(out_path, "wb").write(gz)
    print(f"initramfs: {len(raw)} bytes raw, {len(gz)} bytes gz -> {out_path}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
