import zipfile, os, sys

jar = sys.argv[1]
out = sys.argv[2]
os.makedirs(out, exist_ok=True)
z = zipfile.ZipFile(jar)
for n in z.namelist():
    if n.endswith('/'):
        continue
    dest = os.path.join(out, n.replace('/', '__'))
    with open(dest, 'wb') as f:
        f.write(z.read(n))
    print('EXTRACTED', n, '->', dest, z.getinfo(n).file_size)
