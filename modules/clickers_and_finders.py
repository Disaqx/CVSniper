"""Selenium wrappers for finding and clicking things on LinkedIn.

Every function here is forgiving on purpose. LinkedIn changes its DOM without
warning and renders half the page lazily, so a helper that raises on a missing
element would stop the run over a cosmetic change. These return `False` or
`None` instead and let the caller decide whether the element mattered.

The first argument is typed as WebDriver but any WebElement works too — both
expose `find_element`, and callers routinely scope a search to a single
question block rather than the whole page.
"""

from __future__ import annotations

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from modules.helpers import buffer, critical_error_log, print_lg

try:
    from config.settings import smooth_scroll
except Exception:
    smooth_scroll = True

# Raised when an element is found but the click does not land. Worth retrying
# once after scrolling, because it usually means a sticky header is covering it.
_CLICK_BLOCKED = (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    StaleElementReferenceException,
)

# Everything that simply means "not there"
_NOT_FOUND = (NoSuchElementException, TimeoutException, StaleElementReferenceException)


def _xpath_literal(text: str) -> str:
    """Quote a string for XPath, surviving apostrophes.

    XPath 1.0 has no escape character, so a job title like "Driver's mate"
    cannot be embedded directly — it has to be split and reassembled with
    concat(). Skipping this is the classic source of InvalidSelectorException.
    """
    if "'" not in text:
        return f"'{text}'"
    if '"' not in text:
        return f'"{text}"'
    partes = text.split("'")
    return "concat(" + ", \"'\", ".join(f"'{p}'" for p in partes) + ")"


# ---------------------------------------------------------------------------
# Finders
# ---------------------------------------------------------------------------

def try_xp(driver: WebDriver, xpath: str, click: bool = True) -> WebElement | bool:
    """Find by XPath. Click it when asked. Return the element, or False."""
    try:
        elemento = driver.find_element(By.XPATH, xpath)
        if not click:
            return elemento
        elemento.click()
        return True
    except _CLICK_BLOCKED:
        # Found but covered — scroll it clear and take one more run at it
        try:
            elemento = driver.find_element(By.XPATH, xpath)
            scroll_to_view(driver, elemento)
            elemento.click()
            return True
        except Exception:
            return False
    except Exception:
        return False


def try_linkText(driver: WebDriver, linkText: str) -> WebElement | bool:
    """Click a link by its exact text. Return the element, or False."""
    try:
        elemento = driver.find_element(By.LINK_TEXT, linkText)
        elemento.click()
        return elemento
    except Exception:
        return False


def try_find_by_classes(driver: WebDriver, classes: list[str]) -> WebElement | ValueError:
    """Return the first element matching any of these class names.

    LinkedIn ships several markup variants at once, so callers pass the known
    aliases newest-first and take whichever exists today.
    """
    for nombre in classes or []:
        try:
            return driver.find_element(By.CLASS_NAME, nombre)
        except Exception:
            continue
    raise ValueError(f"None of these classes were found: {classes}")


def find_by_class(driver: WebDriver, class_name: str, time: float = 5.0) -> WebElement | Exception:
    """Wait up to `time` seconds for a class to appear, then return it.

    Raises on timeout: callers use this for elements that must exist, unlike
    the `try_*` helpers.
    """
    return WebDriverWait(driver, time).until(
        EC.presence_of_element_located((By.CLASS_NAME, class_name))
    )


# ---------------------------------------------------------------------------
# Scrolling
# ---------------------------------------------------------------------------

def scroll_to_view(
    driver: WebDriver,
    element: WebElement,
    top: bool = False,
    smooth_scroll: bool = smooth_scroll,
) -> None:
    """Bring an element into view.

    `top` aligns it to the top of the viewport, which matters for LinkedIn's
    modal footers: the default centring can leave a submit button underneath
    the sticky bar, and the click then silently hits the bar instead.
    """
    comportamiento = "smooth" if smooth_scroll else "instant"
    bloque = "start" if top else "center"
    try:
        driver.execute_script(
            "arguments[0].scrollIntoView({behavior: arguments[1], block: arguments[2]});",
            element,
            comportamiento,
            bloque,
        )
        if smooth_scroll:
            # Give the animation time to settle or the click lands mid-flight
            buffer(0.6)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Clickers
# ---------------------------------------------------------------------------

def wait_span_click(
    driver: WebDriver,
    text: str,
    time: float = 5.0,
    click: bool = True,
    scroll: bool = True,
    scrollTop: bool = False,
) -> WebElement | bool:
    """Wait for a <span> with this exact text and click it.

    Most LinkedIn buttons put their label in a nested span, so matching the
    span and clicking it is more reliable than matching the button. Whitespace
    is normalised because the markup is full of stray newlines.
    """
    if not text:
        return False
    xpath = f"//span[normalize-space(.)={_xpath_literal(text)}]"
    try:
        elemento = WebDriverWait(driver, time).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )
        if scroll:
            scroll_to_view(driver, elemento, top=scrollTop)
        if not click:
            return elemento
        try:
            elemento.click()
        except _CLICK_BLOCKED:
            # A parent is usually the real click target
            driver.execute_script("arguments[0].click();", elemento)
        buffer(0.4)
        return elemento
    except _NOT_FOUND:
        return False
    except Exception as e:
        critical_error_log(f"Could not click the span '{text}'", e)
        return False


def wait_button_click(
    driver: WebDriver,
    texts: list[str],
    time: float = 5.0,
    click: bool = True,
    scroll: bool = True,
    scrollTop: bool = False,
) -> WebElement | bool:
    """Click the first button matching ANY of these labels.

    Callers pass the same button in several languages —
    ["Submit application", "Enviar solicitud", "Enviar"] — because LinkedIn
    renders its UI in the account's language, and a bot that only knows the
    English label silently stops at the last step.

    Four strategies per label, cheapest first: the label often sits in a nested
    <span>, sometimes directly on the <button>, and occasionally only in
    aria-label when the visible text is an icon.
    """
    if not texts:
        return False
    if isinstance(texts, str):
        texts = [texts]

    candidatos: list[str] = []
    for texto in texts:
        if not texto:
            continue
        literal = _xpath_literal(str(texto))
        candidatos += [
            f"//button[normalize-space(.)={literal}]",
            f"//span[normalize-space(.)={literal}]/ancestor::button[1]",
            f"//button[@aria-label={literal}]",
            f"//span[normalize-space(.)={literal}]",
        ]

    def _usar(elemento: WebElement) -> WebElement:
        if scroll:
            scroll_to_view(driver, elemento, top=scrollTop)
        if click:
            try:
                elemento.click()
            except _CLICK_BLOCKED:
                driver.execute_script("arguments[0].click();", elemento)
            buffer(0.5)
        return elemento

    # First pass: no waiting. If the button is already rendered — which it is
    # almost every time — this returns immediately instead of paying the poll
    # interval once per label. Waiting on each candidate in turn would blow the
    # caller's timeout by the number of labels times the number of strategies.
    for xpath in candidatos:
        try:
            return _usar(driver.find_element(By.XPATH, xpath))
        except _NOT_FOUND:
            continue
        except Exception as e:
            critical_error_log(f"Could not click the button {texts}", e)
            continue

    # Second pass: the button may still be rendering. Spend the whole budget
    # once, on all candidates at a time, rather than per candidate.
    combinado = " | ".join(candidatos)
    try:
        elemento = WebDriverWait(driver, float(time)).until(
            EC.presence_of_element_located((By.XPATH, combinado))
        )
        return _usar(elemento)
    except _NOT_FOUND:
        pass
    except Exception as e:
        critical_error_log(f"Could not click the button {texts}", e)

    print_lg(f"None of these buttons were found: {texts}")
    return False


def text_input_by_ID(
    driver: WebDriver, id: str, value: str, time: float = 5.0
) -> None | Exception:
    """Type a value into the field with this id, replacing what is there."""
    campo = WebDriverWait(driver, time).until(
        EC.presence_of_element_located((By.ID, id))
    )
    try:
        campo.clear()
    except Exception:
        pass
    campo.send_keys(str(value))


def boolean_button_click(driver: WebDriver, actions: ActionChains, text: str) -> None:
    """Toggle one of LinkedIn's on/off filter pills by its label.

    These are rendered as labels tied to a hidden checkbox, so the input
    itself is not clickable and the label has to be hit instead.
    """
    literal = _xpath_literal(text)
    for xpath in (
        f"//label[normalize-space(.)={literal}]",
        f"//span[normalize-space(.)={literal}]/ancestor::label[1]",
        f"//button[normalize-space(.)={literal}]",
    ):
        try:
            elemento = driver.find_element(By.XPATH, xpath)
            scroll_to_view(driver, elemento)
            try:
                elemento.click()
            except _CLICK_BLOCKED:
                driver.execute_script("arguments[0].click();", elemento)
            buffer(0.4)
            return
        except Exception:
            continue
    print_lg(f"The filter '{text}' was not found, skipping it.")


def multi_sel_noWait(driver: WebDriver, texts: list, actions: ActionChains = None) -> None:
    """Tick several filter options in a row without waiting between them.

    Used for the long checkbox lists in the search filters, where waiting on
    each one would add minutes to every run. Anything missing is reported and
    skipped rather than aborting the rest of the list.
    """
    for texto in texts or []:
        if not texto:
            continue
        literal = _xpath_literal(str(texto))
        try:
            elemento = driver.find_element(
                By.XPATH, f"//span[normalize-space(.)={literal}]"
            )
            if actions is not None:
                try:
                    actions.move_to_element(elemento).click().perform()
                    continue
                except Exception:
                    pass  # fall through to the direct click
            try:
                elemento.click()
            except _CLICK_BLOCKED:
                driver.execute_script("arguments[0].click();", elemento)
        except Exception:
            print_lg(f"The option '{texto}' was not found, skipping it.")
