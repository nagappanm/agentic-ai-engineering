"""Load and validate sources.yaml — fail CLOSED on any invalid entry.

A typo in the user-editable registry must be a red run naming the entry, never a
silently skipped source. Validation also refuses URLs that could steer an unattended
run at private hosts (loopback, link-local, RFC 1918).
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

import yaml
from pydantic import ValidationError

from qe_signals.models import Registry, SourceEntry

REGISTRY_DEFAULT = Path(__file__).with_name("sources.yaml")
PLAYBOOK_DEFAULT = Path(__file__).with_name("dna_playbook.md")

Resolver = Callable[[str], list[str]]


class RegistryError(ValueError):
    """Registry could not be parsed or an entry is invalid."""


def default_resolver(host: str) -> list[str]:
    """Resolve a hostname to its IP address strings (empty list if unresolvable)."""
    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError, OSError):
        return []
    return sorted({info[4][0] for info in infos})


def is_blocked_host(host: str, resolver: Resolver = default_resolver) -> str:
    """Return a reason string if `host` must not be fetched, else ''.

    Blocks loopback, link-local (incl. 169.254.169.254 metadata), private RFC 1918,
    unspecified and multicast ranges — checked on the literal and on every resolved
    address, so DNS pointing at an internal host is refused too.
    """
    if not host:
        return "empty host"
    candidates: list[str] = []
    try:
        ipaddress.ip_address(host.strip("[]"))
        candidates = [host.strip("[]")]
    except ValueError:
        if host.lower() in {"localhost", "localhost.localdomain"}:
            return "loopback host"
        candidates = resolver(host)
    for addr in candidates:
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if ip.is_loopback or ip.is_link_local or ip.is_private or ip.is_unspecified:
            return f"blocked address {addr}"
        if ip.is_multicast or ip.is_reserved:
            return f"blocked address {addr}"
    return ""


def check_url(url: str, resolver: Resolver = default_resolver) -> str:
    """Return a reason string if a URL is not fetchable under policy, else ''."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return f"scheme {parsed.scheme!r} not allowed"
    return is_blocked_host(parsed.hostname or "", resolver)


def load_registry(
    path: Path | None = None,
    *,
    resolver: Resolver = default_resolver,
    check_hosts: bool = True,
) -> Registry:
    """Parse + validate the registry. Raises RegistryError with the offending entry."""
    p = path or REGISTRY_DEFAULT
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    except OSError as e:
        raise RegistryError(f"registry unreadable: {p}: {e}") from e
    except yaml.YAMLError as e:
        raise RegistryError(f"registry YAML error in {p.name}: {e}") from e
    if not isinstance(raw, dict) or "sources" not in raw:
        raise RegistryError(f"registry {p.name} must be a mapping with a 'sources' list")
    try:
        reg = Registry.model_validate(raw)
    except ValidationError as e:
        names = _names_for_errors(raw, e)
        raise RegistryError(f"invalid registry entry {names}: {_first_error(e)}") from e
    if check_hosts:
        for entry in reg.sources:
            reason = check_url(entry.url, resolver)
            if reason:
                raise RegistryError(f"invalid registry entry {entry.name!r}: {reason}")
    return reg


def enabled_sources(reg: Registry) -> list[SourceEntry]:
    return [s for s in reg.sources if s.enabled]


def _names_for_errors(raw: dict, err: ValidationError) -> str:
    seen: list[str] = []
    for e in err.errors():
        loc = e.get("loc", ())
        if len(loc) >= 2 and loc[0] == "sources" and isinstance(loc[1], int):
            item = raw["sources"][loc[1]] if loc[1] < len(raw["sources"]) else {}
            name = item.get("name", f"#{loc[1]}") if isinstance(item, dict) else f"#{loc[1]}"
            if name not in seen:
                seen.append(str(name))
    return ", ".join(repr(n) for n in seen) or "(registry)"


def _first_error(err: ValidationError) -> str:
    e = err.errors()[0]
    return f"{'.'.join(str(x) for x in e.get('loc', ()))}: {e.get('msg')}"
