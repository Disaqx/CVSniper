'''
Keeps the LinkedIn password and the LLM API key out of config/secrets.py.

They go to the operating system's credential store instead (Windows Credential
Manager, macOS Keychain, the Secret Service on Linux) through `keyring`, and
secrets.py holds only a call that fetches them:

    llm_api_key = from_keyring("llm_api_key")

Every `from config.secrets import llm_api_key` in the bot therefore still gets
the real value, with no other code aware of where it came from.

Where no credential store is available (a headless Linux box, `keyring` not
installed) nothing changes: the value stays in secrets.py as plain text, which
is how it always worked.
'''
import ast
import re

SERVICE = "CVSniper"

# The secrets.py variables that are moved to the store.
SECRET_FIELDS = ("password", "llm_api_key")

# Template values: leaving these as literals keeps the "not configured yet"
# checks elsewhere working.
_PLACEHOLDERS = {"", "example_password", "your_password", "not-needed",
                 "YOUR_GROQ_API_KEY_HERE", "YOUR_API_KEY_HERE", "sk-xxx"}

IMPORT_LINE = "from modules.credentials import from_keyring  # password / API key live in the OS credential store\n"


def _keyring():
    '''The keyring module if it has a real backend here, else None.'''
    try:
        import keyring
        from keyring.backends import fail
        if isinstance(keyring.get_keyring(), fail.Keyring):
            return None
        return keyring
    except Exception:
        return None


def available() -> bool:
    return _keyring() is not None


def from_keyring(name: str) -> str:
    '''The stored value, or "" if it is missing or the store cannot be read.'''
    kr = _keyring()
    if kr is None:
        return ""
    try:
        return kr.get_password(SERVICE, name) or ""
    except Exception:
        return ""


def store(name: str, value: str) -> bool:
    '''Save a secret. False if there is no usable store (the caller keeps the plain value).'''
    kr = _keyring()
    if kr is None:
        return False
    try:
        if value:
            kr.set_password(SERVICE, name, value)
        else:
            try:
                kr.delete_password(SERVICE, name)
            except Exception:
                pass
        return True
    except Exception:
        return False


def is_placeholder(value) -> bool:
    return str(value or "").strip() in _PLACEHOLDERS


def keyring_call(node) -> str | None:
    '''If an ast value node is `from_keyring("name")`, return "name".'''
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "from_keyring" and len(node.args) == 1
            and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
        return node.args[0].value
    return None


def with_import(source: str) -> str:
    '''secrets.py source with the from_keyring import at the top, added once.'''
    if re.search(r'^from modules\.credentials import from_keyring', source, re.M):
        return source
    return IMPORT_LINE + source


def migrate_secrets_file(path: str) -> list[str]:
    '''
    Move any plain-text secret in secrets.py into the store and rewrite its line
    as a from_keyring() call. Returns the names moved. Run once at startup; a
    file already migrated, or a machine without a store, is left as it is.
    '''
    try:
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
    except Exception:
        return []
    if not available():
        return []

    lines = source.splitlines(keepends=True)
    movidos = []
    # Bottom-up, so replacing one assignment never shifts the next one's lines.
    nodos = [n for n in tree.body if isinstance(n, ast.Assign) and len(n.targets) == 1
             and isinstance(n.targets[0], ast.Name) and n.targets[0].id in SECRET_FIELDS]
    for nodo in sorted(nodos, key=lambda n: n.lineno, reverse=True):
        nombre = nodo.targets[0].id
        if not (isinstance(nodo.value, ast.Constant) and isinstance(nodo.value.value, str)):
            continue
        valor = nodo.value.value
        if is_placeholder(valor) or not store(nombre, valor):
            continue
        # Keep the comment that followed the value on the same line.
        ultima = lines[nodo.end_lineno - 1]
        resto = ultima[nodo.end_col_offset:].rstrip("\r\n")
        lines[nodo.lineno - 1: nodo.end_lineno] = [f'{nombre} = from_keyring("{nombre}"){resto}\n']
        movidos.append(nombre)

    if movidos:
        with open(path, "w", encoding="utf-8") as f:
            f.write(with_import("".join(lines)))
    return movidos
