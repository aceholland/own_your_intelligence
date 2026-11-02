"""User-scoped Windows credential protection; never persist plaintext on other OSes."""
import ctypes
import json
import os
from pathlib import Path
from ctypes import wintypes

from .store import Problem


class Blob(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_byte))]


def protected_bytes(value, decrypt=False):
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    buffer = ctypes.create_string_buffer(value)
    source = Blob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    result = Blob()
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result)):
        raise OSError(ctypes.get_last_error(), 'Windows credential protection failed')
    try:
        return ctypes.string_at(result.data, result.size)
    finally:
        kernel.LocalFree(result.data)


class CredentialVault:
    def __init__(self, path):
        self.path = Path(path)
        self.memory = None

    def save(self, value):
        if os.name == 'nt':
            encrypted = protected_bytes(json.dumps(value).encode())
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix('.tmp')
            temporary.write_bytes(encrypted)
            temporary.replace(self.path)
        else:
            self.memory = dict(value)

    def load(self):
        if os.name != 'nt':
            return self.memory
        if not self.path.exists():
            return None
        try:
            return json.loads(protected_bytes(self.path.read_bytes(), decrypt=True))
        except (OSError, ValueError) as error:
            raise Problem('The saved GPU connection cannot be unlocked. Reconnect using your current Windows account.') from error

    def clear(self):
        self.memory = None
        self.path.unlink(missing_ok=True)
