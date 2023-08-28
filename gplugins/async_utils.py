from __future__ import annotations

import asyncio
import io
import sys
from collections.abc import Awaitable, Coroutine
from contextlib import nullcontext
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")


async def handle_return(
    in_stream: asyncio.streams.StreamReader,
    out_stream: io.TextIOWrapper | None = None,
    log_file: Path | None = None,
    append: bool = False,
) -> None:
    """Reads through a :class:`StreamReader` and tees content to ``out_stream`` and ``log_file``."""
    with open(
        log_file, "a" if append else "w", encoding="utf-8", buffering=1
    ) if log_file else nullcontext(None) as f:
        while True:
            # Without this sleep, the program won't exit
            await asyncio.sleep(0)
            data = await in_stream.readline()
            if data:
                line = data.decode("utf-8").rstrip()
                if out_stream:
                    print(line, file=out_stream)
                if f:
                    f.write(line + "\n")
            else:
                break


async def execute_and_stream_output(
    command: list[str] | str,
    *args,
    shell: bool = True,
    append: bool = False,
    log_file_dir: Path | None = None,
    log_file_str: str | None = None,
    **kwargs,
) -> asyncio.subprocess.Process:
    """Run a command asynchronously and stream *stdout* and *stderr* to main and a log file
    in ``log_file_dir / log_file_str``. Uses ``shell=True`` as default unlike ``subprocess.Popen``. Returns an asyncio process.

    Args:
        command: Command(s) to run. Sequences will be unpacked.
        shell: Whether to use shell or exec.
        append: Whether to use append to log file instead of writing.
        log_file_dir: Directory for log files.
        log_file_str: Log file name. Will be expanded to ``f'{log_file_str}_out.log'`` and ``f'{log_file_str}_err.log'``.

    ``*args`` and ``**kwargs`` are passed to :func:`~create_subprocess_shell` or :func:`create_subprocess_exec`,
    which in turn passes them to :class:`subprocess.Popen`.
    """
    if log_file_dir is None:
        log_file_dir = Path.cwd()
    if log_file_str is None:
        log_file_str = command if isinstance(command, str) else "_".join(command)

    subprocess_factory = (
        asyncio.create_subprocess_shell if shell else asyncio.create_subprocess_exec
    )
    proc = await subprocess_factory(
        *([command] if isinstance(command, str) else command),
        *args,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        **kwargs,
    )
    asyncio.create_task(
        handle_return(
            proc.stdout,
            out_stream=sys.stdout,
            log_file=log_file_dir / f"{log_file_str}_out.log",
            append=append,
        )
    )
    asyncio.create_task(
        handle_return(
            proc.stderr,
            out_stream=sys.stderr,
            log_file=log_file_dir / f"{log_file_str}_err.log",
            append=append,
        )
    )

    # This needs to also handle the "wait_to_finish" flag
    await proc.wait()
    return proc


def run_async_with_event_loop(coroutine: Coroutine[Any, Any, T] | Awaitable[T]) -> T:
    """Run a coroutine within an asyncio event loop, either by adding it to the
    existing running event loop or by creating a new event loop. Returns the result.

    Args:
        coroutine: The coroutine (async function) to be executed.

    Note:
        If an asyncio event loop is already running, `nest_asyncio <https://github.com/erdewit/nest_asyncio>`_
        is used to create a new loop. the given coroutine will be added to the running event loop.
        If no event loop is running, a new event loop will be created.

    Example:
        async def main():
            # Your main coroutine code here
            pass

        run_async_with_event_loop(main())
    """

    try:
        loop = asyncio.get_running_loop()
        try:
            import nest_asyncio  # pylint: disable=import-outside-toplevel

            nest_asyncio.apply()
        except ModuleNotFoundError as e:
            raise UserWarning(
                "You need to install `nest-asyncio` to run in existing event loops like IPython"
            ) from e
        return loop.run_until_complete(coroutine)
    except RuntimeError as e:
        if "no running event loop" not in str(e):
            raise e
        return asyncio.run(coroutine)
