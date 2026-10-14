"""Unchanged benchmark runner plus before/after hashes of lexical dependencies."""
import argparse
import hashlib
import json
from pathlib import Path

import thai_benchmark as benchmark


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--dataset', type=Path, default=benchmark.DATASET)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'work/thai-benchmark')
    args, _ = parser.parse_known_args()
    paths = [args.dataset, Path(benchmark.__file__), Path(benchmark.ai.__file__),
             Path(benchmark.ai.policy.__file__), Path(benchmark.ai.policy.thai_normalizer.__file__)]
    def hashes():
        return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    before = hashes()
    args.output.mkdir(parents=True, exist_ok=True)
    receipt = args.output / 'source_receipt.json'
    receipt.write_text(json.dumps({'before': before, 'completed': False}, indent=2), encoding='utf-8')
    status = benchmark.main()
    after = hashes()
    receipt.write_text(json.dumps({'before': before, 'after': after, 'completed': True,
                                  'unchanged_during_evaluation': before == after,
                                  'benchmark_exit': status}, indent=2), encoding='utf-8')
    if before != after:
        raise RuntimeError('Evaluation sources changed; result is not a frozen evaluation')
    return status


if __name__ == '__main__':
    raise SystemExit(main())
