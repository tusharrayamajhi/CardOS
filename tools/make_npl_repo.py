"""Build the "NPL Cricket only" repo from this repo, so the app has one source.

    python tools/make_npl_repo.py            -> dist/npl-cricket/
    python tools/make_npl_repo.py <folder>   -> <folder>/

The output boots straight into the NPL app on a stock UIFlow2 Cardputer ADV,
without the CardOS home screen or other apps:
  apps/npl.py + the few cardos/ modules it uses  -> nplkit/ (imports renamed)
  standalone/  (runtime, config, main.py, README) -> as is
  install.py, res/npl, sd/npl, logo/team tools, LICENSE, CREDITS.md
An existing .git folder in the output is kept, so the repo can be rebuilt,
then committed and pushed as usual.
"""
import os
import shutil
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "dist", "npl-cricket"))
SHARED = ("keys", "net", "jsonstream", "sd")      # cardos modules the app needs as is
FILES = ("install.py", "LICENSE", "CREDITS.md", ".gitattributes",
         "tools/npl_logos.py", "tools/npl_teams.py")
TREES = ("res/npl", "sd/npl")


def rename_imports(text):
    return text.replace("from cardos import", "from nplkit import").replace("from cardos.", "from nplkit.")


def write(rel, text):
    path = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def copy(rel_src, rel_dst=None):
    dst = os.path.join(OUT, rel_dst or rel_src)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(os.path.join(ROOT, rel_src), dst)


def main():
    os.makedirs(OUT, exist_ok=True)
    for name in os.listdir(OUT):          # start clean, but keep the git history
        if name == ".git":
            continue
        p = os.path.join(OUT, name)
        shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)

    write("nplkit/__init__.py", "")
    for m in SHARED:
        write("nplkit/%s.py" % m, rename_imports(read("cardos/%s.py" % m)))
    write("nplkit/npl.py", rename_imports(read("apps/npl.py")))
    for dirpath, _, names in os.walk(os.path.join(ROOT, "standalone")):
        for n in names:
            src = os.path.relpath(os.path.join(dirpath, n), ROOT)
            copy(src, os.path.relpath(src, "standalone"))
    for f in FILES:
        copy(f)
    for t in TREES:
        for dirpath, _, names in os.walk(os.path.join(ROOT, t)):
            for n in names:
                copy(os.path.relpath(os.path.join(dirpath, n), ROOT))

    left = [p for p in ("nplkit/npl.py",) + tuple("nplkit/%s.py" % m for m in SHARED)
            if "import cardos" in open(os.path.join(OUT, p), encoding="utf-8").read()
            or "from cardos" in open(os.path.join(OUT, p), encoding="utf-8").read()]
    if left:
        sys.exit("still importing cardos: " + ", ".join(left))
    n = sum(len(files) for d, _, files in os.walk(OUT) if ".git" not in d.split(os.sep))
    print("NPL Cricket repo written to %s (%d files)" % (OUT, n))


if __name__ == "__main__":
    main()
