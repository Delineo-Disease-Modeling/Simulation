"""Binary "patterns" movement format (DLNOPAT1).

The movement schedule ("patterns") is, by construction, a *full population
snapshot* per timestep: every person is at exactly one location at every
timestep (verified empirically — see COLUMNAR_PATTERNS_DESIGN.md). So it encodes
losslessly as a dense matrix ``M[timestep, person] = location_index`` with the
person id implicit in the column. That replaces the ~424 MB JSON blob (~65 s to
parse + ~14 s per-person index loop) with a ~28 MB zstd buffer that decodes via
``np.frombuffer`` + a vectorized id-remap in well under a second.

On-wire layout (all integers little-endian):

    magic        char[8]   b"DLNOPAT1"  (trailing digit = format version)
    layout       u8        0 = full-snapshot dense (1 = delta/CSR, reserved)
    dtype        u8        0 = uint16, 1 = uint32   (matrix value dtype)
    orientation  u8        0 = ts-major [T, N]      (1 = person-major, reserved)
    codec        u8        0 = none, 1 = zstd, 2 = gzip
    T            u32       number of timesteps
    N            u32       number of persons (matrix columns)
    L            u32       number of locations (len(loc_ids))
    n_homes      u32       split point: location index < n_homes is a home
    ts_minutes   u32[T]    the timestep keys in minutes (60, 120, ...)
    pids_len     u32 ; pids_blob    (utf-8, newline-joined person ids; column -> pid)
    locids_len   u32 ; locids_blob  (utf-8, newline-joined location ids; index -> id)
    raw_nbytes   u64       decompressed payload size (= T*N*itemsize), for integrity
    comp_nbytes  u64 ; payload         (the codec frame of the C-order matrix bytes)

The producer (Algorithms) and consumer (Simulation) agree only on this layout,
NOT on a shared integer id space: the producer's own string id tables ride in
the header and the consumer re-maps them through its papdata-built index spaces,
so producer/consumer enumeration order can differ without corruption.
"""
from __future__ import annotations

import struct

import numpy as np

MAGIC = b"DLNOPAT1"

LAYOUT_DENSE = 0

_DTYPE_TO_CODE = {2: 0, 4: 1}          # itemsize -> dtype code
_CODE_TO_DTYPE = {0: np.uint16, 1: np.uint32}

ORIENT_TS_MAJOR = 0

CODEC_NONE, CODEC_ZSTD, CODEC_GZIP = 0, 1, 2

# Header up to (but not including) the variable-length blocks.
_FIXED = struct.Struct("<8sBBBBIIII")


def is_binary_patterns(head: bytes) -> bool:
    """True if a body begins with the binary-patterns magic."""
    return head[: len(MAGIC)] == MAGIC


def _split_id_table(blob: bytes) -> list:
    """Decode a newline-joined id table. Empty blob -> [] (not [''])."""
    return blob.decode("utf-8").split("\n") if blob else []


def _compress(raw: bytes, level: int) -> tuple[int, bytes]:
    """Compress with zstd; fall back to stdlib gzip if zstandard is absent.

    The codec byte makes the choice self-describing, so a buffer produced where
    zstandard is unavailable still decodes everywhere.
    """
    try:
        import zstandard

        return CODEC_ZSTD, zstandard.ZstdCompressor(level=level).compress(raw)
    except ImportError:
        import gzip

        return CODEC_GZIP, gzip.compress(raw, compresslevel=6)


def _decompress(codec: int, blob: bytes, raw_nbytes: int) -> bytes:
    if codec == CODEC_NONE:
        return blob
    if codec == CODEC_ZSTD:
        try:
            import zstandard
        except ImportError as e:
            raise RuntimeError(
                "patterns buffer is zstd-compressed but the 'zstandard' package "
                "is not installed"
            ) from e

        return zstandard.ZstdDecompressor().decompress(blob, max_output_size=raw_nbytes)
    if codec == CODEC_GZIP:
        import gzip

        return gzip.decompress(blob)
    raise ValueError(f"unknown patterns codec byte: {codec}")


class BinaryPatterns:
    """Decoded binary patterns: a dense location-index matrix + decode tables.

    Carries the producer's own id tables (``pids``, ``loc_ids``, ``n_homes``) so
    a consumer can re-map them onto its own index spaces. Supports the dict-like
    ``items()`` the legacy (non-engine) consumers expect, reconstructing each
    timestep's ``{homes, places}`` lazily; the engine path skips that entirely
    via the dense matrix.
    """

    def __init__(
        self,
        loc_matrix: np.ndarray,
        ts_minutes: list[int],
        pids: list[str],
        loc_ids: list[str],
        n_homes: int,
    ) -> None:
        self.loc_matrix = loc_matrix          # [T, N], value = producer location index
        self.ts_minutes = ts_minutes          # length T
        self.pids = pids                      # length N: column -> person id (str)
        self.loc_ids = loc_ids                # length L: location index -> id (str)
        self.n_homes = int(n_homes)

    def _timestep_dict(self, row: int) -> dict:
        """Reconstruct the legacy ``{homes, places}`` shape for one timestep."""
        locs = self.loc_matrix[row]
        pids = self.pids
        loc_ids = self.loc_ids
        n_homes = self.n_homes
        homes: dict = {}
        places: dict = {}
        for col in range(locs.shape[0]):
            lidx = int(locs[col])
            bucket = homes if lidx < n_homes else places
            bucket.setdefault(loc_ids[lidx], []).append(pids[col])
        return {"homes": homes, "places": places}

    def items(self):
        """Yield ``(ts_str, {homes, places})`` per timestep (legacy consumers).

        Within-location member order is the person-column order (the producer's
        person enumeration). The format does not preserve the producer's original
        per-location list order — there is no such order in a person-keyed matrix.
        The engine path is order-independent (a person->loc scatter), so this is
        byte-equivalent there; the non-engine path's RNG *is* order-sensitive, so
        it is byte-equivalent only when the producer's lists already match this
        canonical order (the current producer sorts by person id), and otherwise
        statistically (ensemble) equivalent. See COLUMNAR_PATTERNS_DESIGN.md.
        """
        for row, minute in enumerate(self.ts_minutes):
            yield str(minute), self._timestep_dict(row)


def encode_patterns_binary(
    loc_matrix: np.ndarray,
    ts_minutes,
    pids,
    loc_ids,
    n_homes: int,
    level: int = 3,
) -> bytes:
    """Serialize a dense [T, N] location-index matrix to the binary format."""
    L = len(loc_ids)
    dtype = np.uint16 if L <= 65536 else np.uint32
    if int(loc_matrix.max(initial=0)) >= L:
        raise ValueError("location index in matrix exceeds len(loc_ids)")
    # Force C-order little-endian so the bytes are portable across hosts.
    m = np.ascontiguousarray(loc_matrix, dtype=np.dtype(dtype).newbyteorder("<"))
    T, N = m.shape
    if N != len(pids):
        raise ValueError(f"matrix has {N} columns but {len(pids)} pids")

    raw = m.tobytes()
    codec, payload = _compress(raw, level)

    pids_blob = "\n".join(pids).encode("utf-8")
    locids_blob = "\n".join(loc_ids).encode("utf-8")
    ts_arr = np.asarray(ts_minutes, dtype="<u4")
    if ts_arr.shape[0] != T:
        raise ValueError(f"{T} matrix rows but {ts_arr.shape[0]} ts_minutes")

    out = bytearray()
    out += _FIXED.pack(
        MAGIC, LAYOUT_DENSE, _DTYPE_TO_CODE[np.dtype(dtype).itemsize],
        ORIENT_TS_MAJOR, codec, T, N, L, int(n_homes),
    )
    out += ts_arr.tobytes()
    out += struct.pack("<I", len(pids_blob)) + pids_blob
    out += struct.pack("<I", len(locids_blob)) + locids_blob
    out += struct.pack("<QQ", len(raw), len(payload)) + payload
    return bytes(out)


def decode_patterns_binary(data: bytes) -> BinaryPatterns:
    """Parse the binary format back into a :class:`BinaryPatterns`."""
    if not is_binary_patterns(data):
        raise ValueError("not a DLNOPAT binary patterns buffer")
    magic, layout, dtype_code, orient, codec, T, N, L, n_homes = _FIXED.unpack_from(data, 0)
    if layout != LAYOUT_DENSE or orient != ORIENT_TS_MAJOR:
        raise ValueError(f"unsupported layout/orientation: {layout}/{orient}")
    off = _FIXED.size

    ts_arr = np.frombuffer(data, dtype="<u4", count=T, offset=off)
    off += 4 * T
    ts_minutes = ts_arr.astype(np.int64).tolist()

    (pids_len,) = struct.unpack_from("<I", data, off); off += 4
    pids = _split_id_table(data[off : off + pids_len]); off += pids_len
    (locids_len,) = struct.unpack_from("<I", data, off); off += 4
    loc_ids = _split_id_table(data[off : off + locids_len]); off += locids_len
    if len(pids) != N:
        raise ValueError(f"decoded {len(pids)} pids but matrix has {N} columns")
    if len(loc_ids) != L:
        raise ValueError(f"decoded {len(loc_ids)} loc_ids but header declares L={L}")

    raw_nbytes, comp_nbytes = struct.unpack_from("<QQ", data, off); off += 16
    payload = data[off : off + comp_nbytes]
    raw = _decompress(codec, payload, raw_nbytes)
    if len(raw) != raw_nbytes:
        raise ValueError(f"patterns payload truncated: {len(raw)} != {raw_nbytes}")

    dtype = np.dtype(_CODE_TO_DTYPE[dtype_code]).newbyteorder("<")
    matrix = np.frombuffer(raw, dtype=dtype, count=T * N).reshape(T, N)
    return BinaryPatterns(matrix, ts_minutes, pids, loc_ids, n_homes)


def build_arrays_from_legacy(patterns: dict, papdata: dict):
    """Transcode the legacy ``{ts: {homes, places: {id: [pids]}}}`` shape into the
    dense arrays the binary format stores.

    Person columns and location indices are enumerated from papdata (sorted by
    integer id), homes first then places. Used by the offline transcoder and the
    Algorithms producer reference; the consumer never calls this.
    """
    pids = sorted((str(p) for p in papdata["people"]), key=int)
    homes = sorted((str(h) for h in papdata["homes"]), key=int)
    places = sorted((str(p) for p in papdata["places"]), key=int)
    loc_ids = homes + places
    n_homes = len(homes)

    pid_col = {pid: i for i, pid in enumerate(pids)}
    loc_idx = {(hid, True): i for i, hid in enumerate(homes)}
    loc_idx.update({(pid, False): n_homes + i for i, pid in enumerate(places)})

    ts_minutes = sorted(int(ts) for ts in patterns)
    T, N = len(ts_minutes), len(pids)
    # The sentinel (= len(loc_ids)) must also fit the dtype, so uint16 only holds
    # up to 65535 locations (real indices 0..65534 + sentinel 65535).
    dtype = np.uint16 if len(loc_ids) < 65536 else np.uint32
    # Sentinel L marks "unset"; a true full snapshot leaves none behind.
    sentinel = len(loc_ids)
    M = np.full((T, N), sentinel, dtype=dtype)

    for row, minute in enumerate(ts_minutes):
        data = patterns[str(minute)]
        for poi_type, is_hh in (("homes", True), ("places", False)):
            for loc_id, members in data.get(poi_type, {}).items():
                key = (str(loc_id), is_hh)
                if key not in loc_idx:
                    kind = "home" if is_hh else "place"
                    raise ValueError(
                        f"patterns reference {kind} id {loc_id!r} at minute "
                        f"{minute} not present in papdata"
                    )
                li = loc_idx[key]
                for pid in members:
                    col = pid_col.get(str(pid))
                    if col is not None:
                        M[row, col] = li

    unset = int((M == sentinel).sum())
    if unset:
        raise ValueError(
            f"{unset} (timestep, person) cells unset — patterns is not a full snapshot"
        )
    return M, ts_minutes, pids, loc_ids, n_homes
