'''
Keeps CVSniper up to date.

Two jobs, both run at startup:

1. `check_in_background(notify)` — the old behaviour: tell the user a newer
   release exists and open the download page.
2. `auto_update(notify, status, shutdown)` — the new behaviour asked for in
   2026-11: if this copy was installed with the Windows installer, download the
   new `CVSniper-Setup-X.Y.Z.exe` from GitHub, verify its SHA-256 when GitHub
   publishes one, run it silently (Inno Setup upgrades in place, same AppId, no
   uninstall) and restart the app.

Any failure (offline, rate limit, no installer asset, hash mismatch, source
copy instead of an installed one) falls back to the silent/notify path: the bot
always keeps working. `check_for_updates = False` in config/settings.py turns
the check off; `auto_update = False` turns only the automatic install off.
'''
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

from modules.helpers import print_lg
from modules.version import __version__

REPO = "Disaqx/CVSniper"
RELEASES_URL = f"https://github.com/{REPO}/releases/latest"
_API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
_MAX_INSTALLER_BYTES = 400 * 1024 * 1024   # a setup exe is ~100 MB
_DETACHED = 0x00000008                     # subprocess.DETACHED_PROCESS
_NEW_GROUP = 0x00000200                    # subprocess.CREATE_NEW_PROCESS_GROUP


def _parts(version: str) -> tuple[int, ...]:
    '''"v1.2.10" -> (1, 2, 10). Pre-release suffixes are ignored.'''
    numeros = re.findall(r'\d+', str(version or "").split("-")[0])
    return tuple(int(n) for n in numeros[:3]) or (0,)


def is_newer(remote: str, local: str = __version__) -> bool:
    a, b = _parts(remote), _parts(local)
    largo = max(len(a), len(b))
    return a + (0,) * (largo - len(a)) > b + (0,) * (largo - len(b))


def _request(url: str, timeout: float) -> urllib.request.Request:
    return urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"CVSniper/{__version__}",
    })


def latest_release(timeout: float = 5.0) -> tuple[str, str] | None:
    '''(version, page url) of the latest published release, or None.'''
    info = latest_release_info(timeout=timeout)
    return (info["version"], info["page_url"]) if info else None


def latest_release_info(timeout: float = 5.0) -> dict | None:
    '''Version, page and installer asset of the latest release, or None.

    Returns keys: version, tag, page_url, installer_url, installer_name,
    installer_size, digest ("sha256:..." or "").
    '''
    try:
        with urllib.request.urlopen(_request(_API_URL, timeout), timeout=timeout) as resp:
            datos = json.load(resp)
    except Exception:
        return None
    tag = str(datos.get("tag_name") or "").strip()
    if not tag:
        return None
    version = tag.lstrip("vV")
    activo = _pick_installer_asset(datos.get("assets") or [], version)
    return {
        "version": version,
        "tag": tag,
        "page_url": datos.get("html_url") or RELEASES_URL,
        "installer_url": (activo or {}).get("browser_download_url", ""),
        "installer_name": (activo or {}).get("name", ""),
        "installer_size": int((activo or {}).get("size") or 0),
        "digest": str((activo or {}).get("digest") or ""),
    }


def _pick_installer_asset(assets: list, version: str) -> dict | None:
    '''The setup exe belonging to this release, preferring the exact version.'''
    exes = [
        a for a in assets
        if str(a.get("name", "")).lower().startswith("cvsniper-setup-")
        and str(a.get("name", "")).lower().endswith(".exe")
    ]
    if not exes:
        return None
    esperado = f"cvsniper-setup-{version}.exe".lower()
    for asset in exes:
        if str(asset.get("name", "")).lower() == esperado:
            return asset
    for asset in exes:
        if version and version in str(asset.get("name", "")):
            return asset
    return exes[0]


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for bloque in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(bloque)
    return digest.hexdigest()


def download_installer(info: dict, folder: str | None = None, progress=None,
                       timeout: float = 30.0) -> str | None:
    '''Download the setup exe (reusing an already-downloaded copy). None on failure.'''
    url = info.get("installer_url") or ""
    nombre = info.get("installer_name") or ""
    if not url or not nombre:
        return None
    if not url.lower().startswith("https://"):
        return None
    destino_dir = folder or os.path.join(tempfile.gettempdir(), "CVSniper-update")
    try:
        os.makedirs(destino_dir, exist_ok=True)
    except Exception as e:
        print_lg(f"WARNING: no se pudo crear la carpeta de actualización: {e}")
        return None
    destino = os.path.join(destino_dir, nombre)
    esperado = str(info.get("digest") or "").lower().removeprefix("sha256:")
    if esperado and os.path.isfile(destino):
        try:
            if _sha256(destino) == esperado:
                print_lg(f"Actualización ya descargada y verificada: {destino}")
                return destino
        except Exception:
            pass
    print_lg(f"Descargando CVSniper {info.get('version')} desde GitHub...")
    try:
        req = _request(url, timeout)
        with urllib.request.urlopen(req, timeout=timeout) as resp, open(destino, "wb") as fh:
            total = int(resp.headers.get("Content-Length") or info.get("installer_size") or 0)
            descargado = 0
            ultimo_pct = -10
            while True:
                bloque = resp.read(1024 * 1024)
                if not bloque:
                    break
                fh.write(bloque)
                descargado += len(bloque)
                if descargado > _MAX_INSTALLER_BYTES:
                    raise ValueError("el instalador es demasiado grande")
                if total:
                    pct = int(descargado * 100 / total)
                    if pct >= ultimo_pct + 10:
                        ultimo_pct = pct
                        print_lg(f"  ... {pct}% ({descargado // (1024*1024)} MB)")
                        if progress:
                            progress(descargado, total)
        if esperado and _sha256(destino) != esperado:
            os.remove(destino)
            print_lg("WARNING: el SHA-256 del instalador no coincide; se descarta.")
            return None
        print_lg(f"Instalador descargado en '{destino}'.")
        return destino
    except Exception as e:
        print_lg(f"No se pudo descargar la actualización: {e}")
        try:
            if os.path.exists(destino):
                os.remove(destino)
        except Exception:
            pass
        return None


def installed_dir() -> str | None:
    '''Folder of the installed copy (the one with CVSniper.cmd), or None.'''
    candidatos = []
    exe = os.path.abspath(sys.executable)
    candidatos += [os.path.dirname(exe), os.path.dirname(os.path.dirname(exe)),
                   os.path.dirname(os.path.dirname(os.path.dirname(exe)))]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidatos.append(os.path.join(local, "Programs", "CVSniper"))
    for carpeta in candidatos:
        if carpeta and os.path.isfile(os.path.join(carpeta, "CVSniper.cmd")):
            return carpeta
    return None


def installer_command(installer_path: str, launcher_path: str) -> str:
    '''The `cmd /c` line: silent in-place upgrade, then reopen the bot.

    `/VERYSILENT /SUPPRESSMSGBOXES` keeps it invisible; `/CLOSEAPPLICATIONS
    /FORCECLOSEAPPLICATIONS` let Inno replace files this process still had open
    (the bot has already exited by the time the installer runs); `start /min`
    reopens the app the way the Start-menu shortcut does. The log answers "why
    did the update not take" without a second visit.
    '''
    flags = ("/VERYSILENT /SUPPRESSMSGBOXES /NORESTART "
             "/CLOSEAPPLICATIONS /FORCECLOSEAPPLICATIONS "
             "/LOG=%TEMP%\\CVSniper-update.log")
    return f'"{installer_path}" {flags} & start "" /min "{launcher_path}"'


# A failed silent install (SmartScreen, antivirus, disk full) must not turn into
# a download/restart loop on every launch: the attempt is remembered for a while.
_ATTEMPT_HOURS = 6


def _attempt_path() -> str:
    return os.path.join(tempfile.gettempdir(), "CVSniper-update-attempt.json")


def _recent_failed_attempt(version: str) -> bool:
    try:
        with open(_attempt_path(), "r", encoding="utf-8") as fh:
            datos = json.load(fh)
        return (str(datos.get("version")) == str(version)
                and time.time() - float(datos.get("time", 0)) < _ATTEMPT_HOURS * 3600)
    except Exception:
        return False


def _mark_attempt(version: str) -> None:
    try:
        with open(_attempt_path(), "w", encoding="utf-8") as fh:
            json.dump({"version": str(version), "time": time.time()}, fh)
    except Exception:
        pass


def auto_update(notify, status=None, shutdown=None) -> bool:
    '''Check, download and install a newer release in place.

    Returns True when an installer was launched (the caller should exit); False
    when there was nothing to do or this is not an installed copy. `notify` is
    the old update dialog, used as the fallback when auto-install is not
    possible; `shutdown` releases Chrome/UI before the installer replaces files.
    '''
    if platform.system() != "Windows":
        return False
    try:
        from config.settings import auto_update as activado
    except Exception:
        activado = True
    info = latest_release_info()
    if not info or not is_newer(info["version"]):
        return False
    if not activado:
        notify(info["version"], info["page_url"])
        return False
    destino = installed_dir()
    if not destino:
        # Running from the repo: installing here would put a second copy
        # somewhere else. Keep the notice instead.
        notify(info["version"], info["page_url"])
        return False
    if _recent_failed_attempt(info["version"]):
        print_lg(
            f"La actualización a {info['version']} ya se intentó hace menos de "
            f"{_ATTEMPT_HOURS} h y no llegó a completarse; se avisa en vez de repetirla."
        )
        notify(info["version"], info["page_url"])
        return False
    if status:
        status("Actualizando", f"Descargando CVSniper {info['version']}...")
    instalador = download_installer(
        info,
        progress=lambda hechos, total: status(
            "Actualizando", f"Descargando CVSniper {info['version']}... "
                            f"{int(hechos * 100 / total) if total else 0}%"
        ) if status else None,
    )
    if not instalador:
        notify(info["version"], info["page_url"])
        return False
    lanzador = os.path.join(destino, "CVSniper.cmd")
    print_lg(
        f"Instalando CVSniper {info['version']} en '{destino}' y reiniciando. "
        "El bot se cerrará un momento."
    )
    if status:
        status("Actualizando", f"Instalando CVSniper {info['version']}...")
    comando = installer_command(instalador, lanzador)
    try:
        subprocess.Popen(["cmd.exe", "/c", comando], close_fds=True,
                         creationflags=_DETACHED | _NEW_GROUP)
        _mark_attempt(info["version"])
    except Exception as e:
        print_lg(f"No se pudo lanzar el instalador: {e}")
        notify(info["version"], info["page_url"])
        return False
    time.sleep(0.5)
    if shutdown:
        try:
            shutdown()
        except Exception:
            pass
    try:
        os._exit(0)
    except Exception:
        sys.exit(0)
    return True


def check_in_background(notify) -> None:
    '''Calls notify(version, url) from a daemon thread if a newer release exists.'''
    def _run():
        encontrada = latest_release()
        if encontrada and is_newer(encontrada[0]):
            try:
                notify(*encontrada)
            except Exception:
                pass
    threading.Thread(target=_run, name="update-check", daemon=True).start()
