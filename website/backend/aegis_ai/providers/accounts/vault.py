from __future__ import annotations

import ctypes
import os
import re
from ctypes import wintypes


SERVICE_NAME = "Aegis Provider Account Vault"
SECRET_PATTERN = re.compile(
    r"(?i)(api[_-]?key|access[_-]?token|refresh[_-]?token|id[_-]?token|authorization|secret|password|credential)"
)


class CredentialVaultError(RuntimeError):
    pass


def credential_ref(provider_id: str, auth_mode: str, name: str = "primary") -> str:
    provider = provider_id.strip().lower().replace(" ", "_")
    mode = auth_mode.strip().lower().replace(" ", "_") or "api_key"
    slot = name.strip().lower().replace(" ", "_") or "primary"
    return f"aegis:provider-account:{provider}:{mode}:{slot}"


class CredentialVault:
    """OS credential-store wrapper for provider account secrets.

    SQLite keeps only stable credential references and redacted hints. The
    secret material itself stays in the OS credential manager or an installed
    keyring backend. Aegis intentionally has no plaintext file fallback here.
    """

    def __init__(self, service_name: str = SERVICE_NAME):
        self.service_name = service_name
        self._keyring = self._load_keyring()

    @property
    def available(self) -> bool:
        return self._keyring is not None or os.name == "nt"

    def read_secret(self, ref: str) -> str | None:
        target = self._clean_ref(ref)
        if self._keyring is not None:
            try:
                value = self._keyring.get_password(self.service_name, target)
            except Exception as exc:
                raise CredentialVaultError(f"Credential store read failed: {safe_error(exc)}") from exc
            return value.strip() if isinstance(value, str) and value.strip() else None
        if os.name == "nt":
            return _windows_read_credential(target)
        raise CredentialVaultError("No OS credential store is available for provider accounts.")

    def write_secret(self, ref: str, secret: str) -> None:
        target = self._clean_ref(ref)
        value = secret.strip()
        if not value:
            raise CredentialVaultError("Secret value is required.")
        if self._keyring is not None:
            try:
                self._keyring.set_password(self.service_name, target, value)
            except Exception as exc:
                raise CredentialVaultError(f"Credential store write failed: {safe_error(exc, value)}") from exc
            return
        if os.name == "nt":
            _windows_write_credential(target, target, value)
            return
        raise CredentialVaultError("No OS credential store is available for provider accounts.")

    def delete_secret(self, ref: str) -> bool:
        target = self._clean_ref(ref)
        if self._keyring is not None:
            try:
                existing = self._keyring.get_password(self.service_name, target)
            except Exception as exc:
                raise CredentialVaultError(f"Credential store read failed before delete: {safe_error(exc)}") from exc
            if not (isinstance(existing, str) and existing.strip()):
                return False
            try:
                self._keyring.delete_password(self.service_name, target)
            except Exception as exc:
                raise CredentialVaultError(f"Credential store delete failed: {safe_error(exc)}") from exc
            return True
        if os.name == "nt":
            return _windows_delete_credential(target)
        raise CredentialVaultError("No OS credential store is available for provider accounts.")

    def has_secret(self, ref: str) -> bool:
        return bool(self.read_secret(ref))

    def _clean_ref(self, ref: str) -> str:
        target = ref.strip()
        if not target:
            raise CredentialVaultError("Credential reference is required.")
        return target

    @staticmethod
    def _load_keyring():
        try:
            import keyring  # type: ignore
        except Exception:
            return None
        return keyring


def safe_error(exc: Exception, *sensitive_values: str) -> str:
    message = str(exc).strip()
    message = SECRET_PATTERN.sub("[redacted]", message)
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
        raise CredentialVaultError(f"Windows Credential Manager read failed with error {ctypes.get_last_error()}.")
    try:
        data = ctypes.string_at(credential.contents.CredentialBlob, credential.contents.CredentialBlobSize)
        value = data.decode("utf-16-le", errors="ignore").strip()
        return value or None
    finally:
        advapi32.CredFree(credential)


def _windows_write_credential(target: str, username: str, secret: str) -> None:
    if os.name != "nt":
        raise CredentialVaultError("Windows Credential Manager is unavailable on this OS.")
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
        raise CredentialVaultError(f"Windows Credential Manager write failed with error {ctypes.get_last_error()}.")


def _windows_delete_credential(target: str) -> bool:
    if os.name != "nt":
        return False
    if advapi32.CredDeleteW(target, CRED_TYPE_GENERIC, 0):
        return True
    if ctypes.get_last_error() == ERROR_NOT_FOUND:
        return False
    raise CredentialVaultError(f"Windows Credential Manager delete failed with error {ctypes.get_last_error()}.")
