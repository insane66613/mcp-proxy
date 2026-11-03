"""Cross-platform duplication of an asyncio subprocess stdin writer for tests."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncio


def duplicate_asyncio_pipe_writer(process: asyncio.subprocess.Process) -> int:
    """Retain subprocess stdin independently of asyncio's transport."""
    assert process.stdin is not None
    pipe_handle = process.stdin.transport.get_extra_info("pipe").fileno()
    if os.name != "nt":
        return os.dup(pipe_handle)

    import ctypes  # noqa: PLC0415
    import msvcrt  # noqa: PLC0415
    from ctypes import wintypes  # noqa: PLC0415

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.DuplicateHandle.argtypes = (
        wintypes.HANDLE,
        wintypes.HANDLE,
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.HANDLE),
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD,
    )
    kernel.DuplicateHandle.restype = wintypes.BOOL
    current = kernel.GetCurrentProcess()
    duplicated = wintypes.HANDLE()
    if not kernel.DuplicateHandle(
        current,
        wintypes.HANDLE(pipe_handle),
        current,
        ctypes.byref(duplicated),
        0,
        False,  # noqa: FBT003
        0x00000002,
    ):
        raise OSError(ctypes.get_last_error(), "DuplicateHandle failed")
    try:
        return msvcrt.open_osfhandle(duplicated.value, os.O_WRONLY | os.O_BINARY)
    except BaseException:
        kernel.CloseHandle(duplicated)
        raise


def process_is_running(process_id: int) -> bool:
    """Return whether a Windows PID is still active (including child orphans)."""
    if os.name != "nt":
        raise RuntimeError("Windows-only process check")
    import ctypes  # noqa: PLC0415
    from ctypes import wintypes  # noqa: PLC0415

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.GetExitCodeProcess.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, process_id)  # noqa: FBT003
    if not handle:
        error = ctypes.get_last_error()
        if error in (87, 1168):  # Invalid parameter / not found.
            return False
        raise OSError(error, "OpenProcess failed")
    try:
        code = wintypes.DWORD()
        if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
            raise OSError(ctypes.get_last_error(), "GetExitCodeProcess failed")
        still_active = 259  # Windows STILL_ACTIVE process status.
        return code.value == still_active
    finally:
        kernel.CloseHandle(handle)
