"""Foundation inventory: reuse the sealed gate's DEV read-only collector.

No ingestion, application startup, preservation, migration or cleanup is imported.
Only the output directory changes; predecessor evidence is never overwritten.
"""
import asyncio
import importlib.util
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
PREDECESSOR = OUT.parent / 'c-parallel-generation-safety-v1' / 'inventory_readonly.py'


def collector():
    spec = importlib.util.spec_from_file_location('foundation_readonly_collector', PREDECESSOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OUT = OUT
    return module


if __name__ == '__main__':
    asyncio.run(collector().inventory(sys.argv[1]))
