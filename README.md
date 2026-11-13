# Butterfly on the Nose — make.fun ai-happy-01 entry

A joyful golden retriever puppy in a sunny wildflower meadow at golden
hour, mid-giggle — eyes squeezed happily shut, mouth open, tongue out —
while a bright orange butterfly lands right on its nose. Four more
butterflies drift around it under a low golden sun. Big readable shapes,
a warm palette, no text: it lands at a glance, even at ~300 px.

## How to run

```sh
python3 main.py            # writes entry.png next to main.py
# or, as the harness does:
MAKEFUN_OUTPUT_DIR=/output python3 main.py   # writes /output/entry.png
```

## How it is made

`main.py` is a single self-contained Python 3 program using only the
standard library (`zlib` for the PNG encoder). It draws the image
procedurally — no image files are read, no network is touched — with a
fixed seed (`RNG_SEED = 13112026`), so every run writes byte-identical
output: 1024×1024 PNG, 41,651 bytes, verified identical across two runs
(sha256 `f0551dca85252b37007e98ede7ecd6365c6a8748ede7cc371a2aa5a1493163a8`).

## License

MIT — see `LICENSE`.
