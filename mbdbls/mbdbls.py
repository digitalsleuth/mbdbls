#!/usr/bin/env python3
#
# mbdbls - Parse Manifest.mbdb files from iTunes backup directories
#
# Based on code from "galloglass" and "Robert Munafo" found at:
# http://stackoverflow.com/questions/3085153/how-to-parse-the-manifest-mbdb-file-in-an-ios-4-0-itunes-backup
#
# Modifications by Hal Pomeranz (hal@deer-run.com), 2014-04-27
# This code released under Creative Commons Attribution license (CC BY)
#
# Updated for Python 3 by Corey Forman (https://github.com/digitalsleuth)

__version__ = "2.1.0"
__last_updated__ = "2025-02-02"
__source__ = "https://github.com/digitalsleuth/mbdbls"
__authors__ = "galloglass, Robert Munafo, Hal Pomeranz, Corey Forman (digitalsleuth)"

import sys
import hashlib
import argparse
from time import strftime, localtime, gmtime


def getint(data, offset, intsize):
    """Retrieve an integer (big-endian) and new offset from the current offset"""
    value = 0
    while intsize > 0:
        value = (value << 8) + data[offset]
        offset = offset + 1
        intsize = intsize - 1
    return value, offset


def getstring(data, offset):
    """Retrieve a string and new offset from the current offset into the data"""
    if data[offset] == 255 and data[offset + 1] == 255:
        return "", offset + 2  # Blank string
    length, offset = getint(data, offset, 2)  # 2-byte length
    value = data[offset : offset + length]
    return value.decode("ISO-8859-1"), (offset + length)


def process_mbdb_file(filename, sort_fld, sort_fmt):
    mbdb = {}  # Map offset of info in this file => file info
    sorting = {}
    with open(filename, "rb") as content:
        data = content.read()
        if data[0:4] != b"mbdb":
            return False, "This does not look like an MBDB file"
        offset = 4
        offset = offset + 2  # value x05 x00, not sure what this is
        while offset < len(data):
            fileinfo = {}
            fileinfo["start_offset"] = offset
            fileinfo["domain"], offset = getstring(data, offset)
            fileinfo["filename"], offset = getstring(data, offset)
            fileinfo["fullpath"] = fileinfo["domain"] + "::" + fileinfo["filename"]
            fileinfo["fileID"] = hashlib.sha1(
                (fileinfo["domain"] + "-" + fileinfo["filename"]).encode()
            ).hexdigest()
            fileinfo["linktarget"], offset = getstring(data, offset)
            fileinfo["datahash"], offset = getstring(data, offset)
            fileinfo["unknown1"], offset = getstring(data, offset)
            fileinfo["mode"], offset = getint(data, offset, 2)
            fileinfo["unknown2"], offset = getint(data, offset, 4)
            fileinfo["unknown3"], offset = getint(data, offset, 4)
            fileinfo["userid"], offset = getint(data, offset, 4)
            fileinfo["groupid"], offset = getint(data, offset, 4)
            fileinfo["mtime"], offset = getint(data, offset, 4)
            fileinfo["atime"], offset = getint(data, offset, 4)
            fileinfo["ctime"], offset = getint(data, offset, 4)
            fileinfo["filelen"], offset = getint(data, offset, 8)
            fileinfo["flag"], offset = getint(data, offset, 1)
            fileinfo["numprops"], offset = getint(data, offset, 1)
            fileinfo["properties"] = {}
            for _ in range(fileinfo["numprops"]):
                propname, offset = getstring(data, offset)
                propval, offset = getstring(data, offset)
                fileinfo["properties"][propname] = propval
    
            mbdb[fileinfo["start_offset"]] = fileinfo
            sorting[fileinfo["start_offset"]] = sort_fmt % (fileinfo[sort_fld])
    return mbdb, sorting


def modestr(val):
    def mode(val):
        if val & 0x4:
            r = "r"
        else:
            r = "-"
        if val & 0x2:
            w = "w"
        else:
            w = "-"
        if val & 0x1:
            x = "x"
        else:
            x = "-"
        return r + w + x

    return mode(val >> 6) + mode((val >> 3)) + mode(val)


def timestr(val, args):
    if args.time_fmt == "e":
        return f"{val:10d}"

    if args.time_fmt == "u":
        tv = gmtime(val)
    else:
        tv = localtime(val)
    return strftime("%Y-%m-%d %H:%M:%S", tv)


def fileinfo_str(f, args):
    if args.s:
        return f["fullpath"]
    if not args.l:
        return f'{f["fileID"]} {f["fullpath"]}'

    if args.tab:
        fmt_str = "%s%s\t%d\t%d\t%d\t%s\t%s\t%s\t%s\t%s\t%s"
        sep_chr = "\t"
    else:
        fmt_str = "%s%s %5d %5d %7d %s  %s  %s  %s %s::%s"
        sep_chr = " "

    if (f["mode"] & 0xE000) == 0xA000:
        file_type = "l"  # symlink
    elif (f["mode"] & 0xE000) == 0x8000:
        file_type = "-"  # file
    elif (f["mode"] & 0xE000) == 0x4000:
        file_type = "d"  # dir
    else:
        print(
            sys.stderr,
            f'Unknown file type {f["mode"]:04x} for {fileinfo_str(f, False)}',
        )
        file_type = "?"  # unknown
    info = fmt_str % (
        file_type,
        modestr(f["mode"] & 0x0FFF),
        f["userid"],
        f["groupid"],
        f["filelen"],
        timestr(f["mtime"], args),
        timestr(f["atime"], args),
        timestr(f["ctime"], args),
        f["fileID"],
        f["domain"],
        f["filename"],
    )
    if file_type == "l":
        info = f'{info} -> {f["linktarget"]}'  # symlink destination
    for name, value in f["properties"].items():  # extra properties
        info = f'{info}{sep_chr}{name}={repr(value)}'
    return info


def main():
    parser = argparse.ArgumentParser(
        description="Parse Manifest.mbdb files from iTunes backup directories"
    )
    parser.add_argument(
        "-f",
        "--file",
        metavar="FILE",
        help="File to parse (default Manifest.mbdb)",
        required=True,
    )
    parser.add_argument(
        "--tab", action="store_true", help="tab-delimited output (implies -l)"
    )
    parser.add_argument(
        "-T",
        "--time_fmt",
        choices=["l", "e", "u"],
        default="l",
        help="Output (l)ocaltime, (u)tc, (e)poch (default localtime)",
    )
    parser.add_argument(
        "-v", "--version", action="version", version="%(prog)s " + str(__version__)
    )

    output_fmt = parser.add_mutually_exclusive_group()
    output_fmt.add_argument("-l", action="store_true", help="detailed listing")
    output_fmt.add_argument("-s", action="store_true", help="display file paths only")

    sort_type = parser.add_mutually_exclusive_group()
    sort_type.add_argument("-t", choices=["m", "a", "c"], help="Sort by m/a/c time")
    sort_type.add_argument("-S", action="store_true", help="Sort by file size")
    parser.add_argument("-r", action="store_false", help="Reverse sort order")

    args = parser.parse_args()

    if args.tab:
        args.l = True
        args.s = False

    sorting = {}
    if args.S:
        sort_fld = "filelen"
        sort_fmt = "%010d"
    elif args.t == "m":
        sort_fld = "mtime"
        sort_fmt = "%010d"
    elif args.t == "a":
        sort_fld = "atime"
        sort_fmt = "%010d"
    elif args.t == "c":
        sort_fld = "ctime"
        sort_fmt = "%010d"
    else:
        sort_fld = "fullpath"
        sort_fmt = "%s"
        args.r = not args.r

    mbdb, sorting = process_mbdb_file(args.file, sort_fld, sort_fmt)
    if mbdb is False:
        print(f"[!] Error: {sorting}")
        sys.exit(1)
    for offset in sorted(sorting, key=sorting.get, reverse=args.r):
        print(fileinfo_str(mbdb[offset], args))


if __name__ == "__main__":
    main()
