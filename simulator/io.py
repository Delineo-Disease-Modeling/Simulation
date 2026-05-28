import gzip
import os

# Snapshot values are pure JSON-native (str/int/list, str-keyed dicts), so the
# serializer only needs the common path. orjson is ~2-4x faster than the stdlib
# json encoder on this shape; fall back to stdlib json (compact) when it isn't
# installed so the simulator still runs. Both emit bytes for the gzip stream.
try:
    import orjson

    def _dumps(obj) -> bytes:
        return orjson.dumps(obj)

    HAVE_ORJSON = True
except ImportError:  # pragma: no cover - exercised only without orjson
    import json

    def _dumps(obj) -> bytes:
        return json.dumps(obj, separators=(",", ":")).encode("utf-8")

    HAVE_ORJSON = False

# gzip's default compresslevel is 9 (maximum). At ZIP 74002 / 168h that costs
# ~47s of pure compression CPU per simulation. Level 1 is the fastest gzip
# level: ~5x faster (verified end-to-end in a controlled microbenchmark on
# real simdata/patterns), ~20% larger output. The output is still a valid
# gzip stream, fully readable by any consumer. Override via DELINEO_GZIP_LEVEL.
_DEFAULT_GZIP_LEVEL = int(os.getenv("DELINEO_GZIP_LEVEL", "1"))


class IncrementalJSONWriter:
    def __init__(self, filename, compresslevel=None):
        self.filename = filename
        level = _DEFAULT_GZIP_LEVEL if compresslevel is None else compresslevel

        # Binary mode: orjson emits bytes (and the json fallback is encoded to
        # utf-8 bytes), and the structural tokens are written as bytes too.
        self.f = gzip.open(filename, "wb", compresslevel=level)
        self.f.write(b"{")
        self.first = True

    def add(self, key, value):
        if not self.first:
            self.f.write(b",")
        else:
            self.first = False

        # Serialize the key as a proper JSON string (handles escaping) followed
        # by the value. We structure the pair manually to avoid materializing
        # one huge wrapper dict across all timesteps.
        self.f.write(_dumps(str(key)))
        self.f.write(b":")
        self.f.write(_dumps(value))

    def close(self):
        self.f.write(b"}")
        self.f.close()
