from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

from .diagnostics import redact_inline


SERVICE_NAME = "Aegis Core Hybrid Model Router"


class CredentialStoreError(RuntimeError):
    pass


def credential_target(provider_id: str) -> str:
    return f"aegis-core:model-provider:{provider_id.strip().lower()}"


class CredentialStore:
    """Small OS credential-store wrapper.

    API keys must not be written into `.aegis/config.json`. This wrapper uses
    Python keyring when available and falls back to Windows Credential Manager
    on Windows hosts. Other hosts without keyring report an unavailable secure
    store rather than silently writing plaintext.
    """

    def __init__(self, service_name: str = SERVICE_NAME):
        self.service_name = service_name
        self._keyring = self._load_keyring()

    @property
    def available(self) -> bool:
        return self._keyring is not None or os.name == "nt"

    def read_provider_key(self, provider_id: str) -> str | None:
        provider = provider_id.strip().lower()
        if not provider:
            return None
        if self._keyring is not None:
            try:
                value = self._keyring.get_password(self.service_name, provider)
            except Exception as exc:
                raise CredentialStoreError(f"OS credential store read failed: {_safe_backend_error(exc)}") from exc
            return value.strip() if isinstance(value, str) and value.strip() else None
        if os.name == "nt":
            return _windows_read_credential(credential_target(provider))
        raise CredentialStoreError("No OS credential store is available. Install keyring or use Windows Credential Manager.")

    def write_provider_key(self, provider_id: str, api_key: str) -> None:
        provider = provider_id.strip().lower()
        key = api_key.strip()
        if not provider:
            raise CredentialStoreError("Provider id is required.")
        if not key:
            raise CredentialStoreError("API key is required.")
        if self._keyring is not None:
            try:
                self._keyring.set_password(self.service_name, provider, key)
            except Exception as exc:
                raise CredentialStoreError(f"OS credential store write failed: {_safe_backend_error(exc, key)}") from exc
            return
        if os.name == "nt":
            _windows_write_credential(credential_target(provider), provider, key)
            return
        raise CredentialStoreError("No OS credential store is available. Install keyring or use Windows Credential Manager.")

    def delete_provider_key(self, provider_id: str) -> bool:
        provider = provider_id.strip().lower()
        if not provider:
            return False
        if self._keyring is not None:
            try:
                existing = self._keyring.get_password(self.service_name, provider)
            except Exception as exc:
                raise CredentialStoreError(f"OS credential store read failed before delete: {_safe_backend_error(exc)}") from exc
            if not (isinstance(existing, str) and existing.strip()):
                return False
            try:
                self._keyring.delete_password(self.service_name, provider)
                return True
            except Exception as exc:
                raise CredentialStoreError(f"OS credential store delete failed: {_safe_backend_error(exc)}") from exc
        if os.name == "nt":
            return _windows_delete_credential(credential_target(provider))
        raise CredentialStoreError("No OS credential store is available. Install keyring or use Windows Credential Manager.")

    def has_provider_key(self, provider_id: str) -> bool:
        return bool(self.read_provider_key(provider_id))

    @staticmethod
    def _load_keyring():
        try:
            import keyring  # type: ignore
        except Exception:
            return None
        return keyring


def _safe_backend_error(exc: Exception, *sensitive_values: str) -> str:
    message = redact_inline(str(exc)).strip()
    for value in sensitive_values:
        if value:
            message = message.replace(value, "[redacted]")
    return message or exc.__class__.__name__


if os.name == "nt":
    CRED_TYPE_GENERIC = 1
    CRED_PERSIST_LOCAL_MACHINE = 2
    ERROR_NOT_FOUND = 1168

    class CREDENTIALW(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD),
            ("Type", wintypes.DWORD),
            ("TargetName", wintypes.LPWSTR),
            ("Comment", wintypes.LPWSTR),
            ("LastWritten", wintypes.FILETIME),
            ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.POINTER(wintypes.BYTE)),
            ("Persist", wintypes.DWORD),
            ("AttributeCount", wintypes.DWORD),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", wintypes.LPWSTR),
            ("UserName", wintypes.LPWSTR),
        ]

    PCREDENTIALW = ctypes.POINTER(CREDENTIALW)
    advapi32 = ctypes.WinDLL("Advapi32", use_last_error=True)
    advapi32.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(PCREDENTIALW)]
    advapi32.CredReadW.restype = wintypes.BOOL
    advapi32.CredWriteW.argtypes = [ctypes.POINTER(CREDENTIALW), wintypes.DWORD]
    advapi32.CredWriteW.restype = wintypes.BOOL
    advapi32.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
    advapi32.CredDeleteW.restype = wintypes.BOOL
    advapi32.CredFree.argtypes = [ctypes.c_void_p]
    advapi32.CredFree.restype = None


def _windows_read_credential(target: str) -> str | None:
    if os.name != "nt":
        return None
    credential = PCREDENTIALW()
    if not advapi32.CredReadW(target, CRED_TYPE_GENERIC, 0, ctypes.byref(credential)):
        if ctypes.get_last_error() == ERROR_NOT_FOUND:
            return None
        raise CredentialStoreError(f"Windows Credential Manager read failed with error {ctypes.get_last_error()}.")
    try:
        data = ctypes.string_at(credential.contents.CredentialBlob, credential.contents.CredentialBlobSize)
        value = data.decode("utf-16-le", errors="ignore").strip()
        return value or None
    finally:
        advapi32.CredFree(credential)


def _windows_write_credential(target: str, username: str, secret: str) -> None:
    if os.name != "nt":
        raise CredentialStoreError("Windows Credential Manager is unavailable on this OS.")
    blob = secret.encode("utf-16-le")
    blob_buffer = ctypes.create_string_buffer(blob)
    credential = CREDENTIALW()
    credential.Type = CRED_TYPE_GENERIC
    credential.TargetName = target
    credential.UserName = username
    credential.CredentialBlob = ctypes.cast(blob_buffer, ctypes.POINTER(wintypes.BYTE))
    credential.CredentialBlobSize = len(blob)
    credential.Persist = CRED_PERSIST_LOCAL_MACHINE
    if not advapi32.CredWriteW(ctypes.byref(credential), 0):
        raise CredentialStoreError(f"Windows Credential Manager write failed with error {ctypes.get_last_error()}.")


def _windows_delete_credential(target: str) -> bool:
    if os.name != "nt":
        return False
    if advapi32.CredDeleteW(target, CRED_TYPE_GENERIC, 0):
        return True
    if ctypes.get_last_error() == ERROR_NOT_FOUND:
        return False
    raise CredentialStoreError(f"Windows Credential Manager delete failed with error {ctypes.get_last_error()}.")
