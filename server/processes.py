"""Owned-process lifetime and single-server locking, including Windows."""
import os
import signal
import subprocess


def kill_tree(process):
    if process.poll() is None:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                           capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.wait(timeout=10)


class InstanceLock:
    def __init__(self, path):
        self.file = open(path, 'a+b')
        try:
            self.file.seek(0, os.SEEK_END)
            if self.file.tell() == 0:
                self.file.write(b'0')
                self.file.flush()
            self.file.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            raise RuntimeError('A build server is already using this data directory.')

    def close(self):
        self.file.close()


class ProcessGuard:
    """Close a Windows job object on server exit to kill orphaned build children."""
    def __init__(self, process):
        self.handle = None
        if os.name != 'nt':
            return
        import ctypes as c
        from ctypes import wintypes as w
        class Basic(c.Structure):
            _fields_ = [('process_time', c.c_int64), ('job_time', c.c_int64), ('flags', w.DWORD),
                        ('min_working', c.c_size_t), ('max_working', c.c_size_t), ('active', w.DWORD),
                        ('affinity', c.c_size_t), ('priority', w.DWORD), ('scheduling', w.DWORD)]
        class IO(c.Structure):
            _fields_ = [(name, c.c_uint64) for name in ('read_ops', 'write_ops', 'other_ops', 'read_bytes', 'write_bytes', 'other_bytes')]
        class Limits(c.Structure):
            _fields_ = [('basic', Basic), ('io', IO), ('process_memory', c.c_size_t), ('job_memory', c.c_size_t),
                        ('peak_process', c.c_size_t), ('peak_job', c.c_size_t)]
        kernel = c.WinDLL('kernel32', use_last_error=True)
        kernel.CreateJobObjectW.argtypes = (c.c_void_p, w.LPCWSTR)
        kernel.CreateJobObjectW.restype = w.HANDLE
        kernel.SetInformationJobObject.argtypes = (w.HANDLE, c.c_int, c.c_void_p, w.DWORD)
        kernel.AssignProcessToJobObject.argtypes = (w.HANDLE, w.HANDLE)
        kernel.CloseHandle.argtypes = (w.HANDLE,)
        handle = kernel.CreateJobObjectW(None, None)
        limits = Limits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not handle or not kernel.SetInformationJobObject(handle, 9, c.byref(limits), c.sizeof(limits)) or not kernel.AssignProcessToJobObject(handle, w.HANDLE(int(process._handle))):
            if handle:
                kernel.CloseHandle(handle)
            kill_tree(process)
            raise OSError('Cannot establish build process lifetime protection.')
        self.handle, self.kernel = handle, kernel

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None
