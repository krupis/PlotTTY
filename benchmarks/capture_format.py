"""Measure conversion, lossless round trips, reads, and recording batches.

Run from the repository root:
  python benchmarks/capture_format.py logs/capture.csv --output logs/capture_benchmark
"""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import struct
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules.core.binary_logging import BinaryCaptureWriter, iter_binary_capture
from modules.core.models import CapturedValue


def iter_csv(path):
    """Benchmark-only reader for historical recordings; not part of the app."""
    with path.open(newline="", encoding="utf-8") as file:
        batch = []
        for row in csv.DictReader(file):
            batch.append(CapturedValue(float(row["timestamp"]), row["label"], float(row["value"]), row["unit"], row["raw_text"]))
            if len(batch) >= 1000:
                yield batch
                batch = []
        if batch:
            yield batch


def iter_plot_batches(path):
    yield from (iter_csv(path) if path.suffix == ".csv" else iter_binary_capture(path))


def inspect(path):
    digest = hashlib.sha256()
    count = 0
    start = perf_counter()
    for batch in iter_plot_batches(path):
        for value in batch:
            digest.update(struct.pack('<dd', value.timestamp, value.value))
            for text in (value.label, value.unit, value.raw_text):
                encoded = text.encode('utf-8')
                digest.update(struct.pack('<I', len(encoded)))
                digest.update(encoded)
            count += 1
    return {'rows': count, 'sha256_fields': digest.hexdigest(), 'read_and_hash_s': perf_counter() - start}


def recording(sample, output, binary):
    timings = []
    start = perf_counter()
    options = {} if binary else {'encoding': 'utf-8', 'newline': ''}
    with output.open('wb' if binary else 'w', **options) as file:
        writer = BinaryCaptureWriter(file) if binary else csv.writer(file)
        for offset in range(0, len(sample), 120):
            batch = sample[offset:offset + 120]
            tick = perf_counter()
            if binary:
                writer.write_values(batch)
                # Simulate a one-second flush at 12,000 values/second.
                if offset % 12000 == 0:
                    writer.flush()
            else:
                writer.writerows((v.timestamp, v.label, v.value, v.unit, v.raw_text) for v in batch)
            timings.append((perf_counter() - tick) * 1000)
        if binary:
            writer.finish()
    timings.sort()
    return {'elapsed_s': perf_counter() - start, 'batch_p95_ms': timings[int(len(timings) * .95)],
            'batch_max_ms': max(timings), 'bytes': output.stat().st_size}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    capture = args.output / 'converted.plotty'
    if capture.exists():
        parser.error(f'{capture} already exists; choose a new output directory')
    started = perf_counter()
    count = 0
    with capture.open('xb') as file:
        writer = BinaryCaptureWriter(file)
        for batch in iter_csv(args.source):
            writer.write_values(batch)
            count += len(batch)
        writer.finish()
    result = {'source': str(args.source), 'source_bytes': args.source.stat().st_size,
              'capture_bytes': capture.stat().st_size, 'convert_s': perf_counter() - started, 'values': count}
    print(json.dumps(result), flush=True)
    result['csv'] = inspect(args.source)
    result['binary'] = inspect(capture)
    assert result['csv']['sha256_fields'] == result['binary']['sha256_fields']
    assert result['csv']['rows'] == result['binary']['rows'] == count
    sample = []
    for batch in iter_plot_batches(args.source):
        sample.extend(batch)
        if len(sample) >= 120000:
            break
    result['record_csv'] = recording(sample, args.output / 'record.csv', False)
    result['record_binary'] = recording(sample, args.output / 'record.plotty', True)
    (args.output / 'result.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
