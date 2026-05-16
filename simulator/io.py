import gzip
import json
import os

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

        # Use gzip.open for compressed writing
        self.f = gzip.open(filename, 'wt', encoding='utf-8', compresslevel=level)
        self.f.write('{')
        self.first = True

    def add(self, key, value):
        if not self.first:
            self.f.write(',')
        else:
            self.first = False

        # We manually structure the key-value pair to avoid dumping a huge wrapper dict
        self.f.write(f'"{key}":')
        json.dump(value, self.f)

    def close(self):
        self.f.write('}')
        self.f.close()
