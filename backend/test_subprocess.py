#!/usr/bin/env python3
"""Test subprocess output reading."""

import asyncio
import sys

async def test_readline():
    """Test async for line in stdout."""
    cmd = [
        "claude",
        "-p", "Say hello",
        "--model", "sonnet",
        "--output-format", "stream-json",
        "--verbose",
    ]

    print(f"Testing readline approach...", flush=True)

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    print(f"Process PID: {process.pid}", flush=True)
    print("Starting async for loop...", flush=True)

    lines_read = 0
    try:
        async for line in process.stdout:
            lines_read += 1
            decoded = line.decode().strip()
            print(f"[LINE {lines_read}] {decoded[:100]}...", flush=True)
            if lines_read >= 5:
                break
    except Exception as e:
        print(f"Error: {e}", flush=True)

    print(f"Total lines read: {lines_read}", flush=True)

    process.terminate()
    await process.wait()

async def test_read_explicit():
    """Test explicit read with buffer size."""
    cmd = [
        "claude",
        "-p", "Say hello",
        "--model", "sonnet",
        "--output-format", "stream-json",
        "--verbose",
    ]

    print(f"\nTesting explicit read approach...", flush=True)

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    print(f"Process PID: {process.pid}", flush=True)

    # Read chunks instead of lines
    total_bytes = 0
    chunks = 0
    while True:
        try:
            chunk = await asyncio.wait_for(process.stdout.read(4096), timeout=10.0)
            if not chunk:
                break
            chunks += 1
            total_bytes += len(chunk)
            print(f"[CHUNK {chunks}] {len(chunk)} bytes: {chunk[:100]}...", flush=True)
            if chunks >= 3:
                break
        except asyncio.TimeoutError:
            print("Read timeout", flush=True)
            break

    print(f"Total: {chunks} chunks, {total_bytes} bytes", flush=True)

    process.terminate()
    await process.wait()

if __name__ == "__main__":
    print("=" * 50, flush=True)
    asyncio.run(test_readline())
    print("=" * 50, flush=True)
    asyncio.run(test_read_explicit())
