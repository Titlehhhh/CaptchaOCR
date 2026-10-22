import os, sys, struct, zlib
from PIL import Image

def chunks(path):
    data = open(path, "rb").read()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not png"
    i = 8
    out = []
    while i < len(data):
        ln = struct.unpack(">I", data[i:i+4])[0]
        typ = data[i+4:i+8].decode("latin1")
        body = data[i+8:i+8+ln]
        if typ in ("tEXt", "iTXt", "zTXt", "eXIf", "iCCP", "pHYs", "tIME", "gAMA", "sRGB"):
            if typ == "zTXt":
                txt = zlib.decompress(body[1:]).decode("latin1", "replace")
            elif typ == "iTXt":
                txt = repr(body[:200])
            else:
                txt = repr(body[:300])
            out.append(f"{typ}: {txt}")
        elif typ == "IHDR":
            w, h, bd, ct = struct.unpack(">IIBB", body[:10])
            out.append(f"IHDR: {w}x{h} bitdepth={bd} colortype={ct}")
        i += 12 + ln
    return out

for p in sys.argv[1:]:
    print("==", p)
    for c in chunks(p):
        print("   ", c)
    try:
        im = Image.open(p)
        print("    PIL info:", {k: v for k, v in im.info.items() if k != "icc_profile"})
    except Exception as e:
        print("    err", e)
