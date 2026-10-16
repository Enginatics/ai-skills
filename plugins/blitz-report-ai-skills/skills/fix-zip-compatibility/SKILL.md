---
name: fix-zip-compatibility
description: Re-compress a ZIP file for Oracle compatibility. Use when Oracle unzip (UTL_COMPRESS/XXEN_REPORT) fails on a ZIP created by Windows 11 or other tools that use data descriptors, ZIP64, or non-standard extra fields.
metadata:
  title: ZIP Compatibility Fix
  category: Testing and Tuning
---

# Fix ZIP Compatibility Skill

Re-compresses a ZIP file to ensure compatibility with Oracle's unzipping routines (UTL_COMPRESS, XXEN_REPORT, etc.). Windows 11 and some Linux tools create ZIPs with features that Oracle cannot parse.

## When to Use

- Oracle reports "invalid zip" or fails to extract a ZIP file
- ZIP was created on Windows 11 (built-in "Compress to ZIP") or Linux
- Upload processing fails during ZIP extraction on the EBS server

## Known Incompatibilities

| Feature | Problem |
|---------|---------|
| **Data descriptor (bit 3)** | Compressed/uncompressed sizes are 0 in the local file header; actual sizes trail the file data. Windows 11 Explorer's Compress to > ZIP File writes this. Builds of XXEN_REPORT that read the sizes from the local header fail with `ORA-21560: argument 3 is null, invalid, or out of range` at `SYS.DBMS_LOB`; current builds read them from the central directory. |
| **ZIP64 extensions** | Extended headers for files >4GB. Oracle's routines may not parse ZIP64 end-of-central-directory records. |
| **Unix extra fields** (`0x7875` UID/GID, `0x5455` timestamps) | Non-standard extra field tags that Oracle may choke on. |
| **UTF-8 flag (bit 11)** | Filenames encoded as UTF-8 instead of CP437. May cause name mismatch. |

## Fix Procedure

Run this Python script to re-create the ZIP with maximum Oracle compatibility:

```python
import zipfile, os, sys

src = sys.argv[1]  # input zip path
dst = sys.argv[2] if len(sys.argv) > 2 else src.replace('.zip', '_fixed.zip')

with zipfile.ZipFile(src, 'r') as zin:
    with zipfile.ZipFile(dst, 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=False) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            # Create clean ZipInfo — no extra fields, no data descriptor
            new_info = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            new_info.compress_type = zipfile.ZIP_DEFLATED
            zout.writestr(new_info, data)

print(f'Fixed: {dst}')
```

### What the fix does

1. **Clears data descriptor flag (bit 3)** — sizes written directly in local file header
2. **Removes Unix extra fields** — no `0x7875` or `0x5455` tags
3. **Disables ZIP64** — standard 32-bit headers only
4. **Standard Deflate compression** — method 8, version 2.0

### Verification

After fixing, verify the output:

```python
import zipfile, struct

with open('fixed.zip', 'rb') as f:
    f.read(4)  # skip signature
    header = f.read(26)
    ver, flags, method = struct.unpack('<HHH', header[:6])
    print(f'Flags: {flags:#06x}, Data descriptor: {bool(flags & 8)}, Method: {method}')
    # Expect: Flags: 0x0000, Data descriptor: False, Method: 8
```

## Diagnostic: Check a ZIP Before Fixing

```python
import zipfile

zf = zipfile.ZipFile('suspect.zip', 'r')
for info in zf.infolist():
    method = {0: 'Stored', 8: 'Deflated', 9: 'Deflate64', 12: 'BZIP2', 14: 'LZMA'}.get(
        info.compress_type, f'Unknown({info.compress_type})')
    print(f'{info.filename}: method={method}, version={info.create_version}')
zf.close()
```

## XXEN_REPORT ZIP Parsing Context

The Blitz Report ZIP parsing logic reads local file headers sequentially, expecting:
- CRC and sizes from the central directory entry (older builds: from the local file header, so a data descriptor fails there)
- Standard Deflate (method 8) or Stored (method 0)
- No ZIP64 extended information extra fields
