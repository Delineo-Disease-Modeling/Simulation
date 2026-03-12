import gzip
import json

class IncrementalJSONWriter:
    def __init__(self, filename):
        self.filename = filename

        # Use gzip.open for compressed writing
        self.f = gzip.open(filename, 'wt', encoding='utf-8')
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
