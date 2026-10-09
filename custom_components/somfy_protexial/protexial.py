import asyncio
import json
import logging
import re
import string
import html as html_lib
import unicodedata

from urllib.parse import urlencode
from xml.etree import ElementTree as ET
from aiohttp import ClientError, ClientSession
from pyquery import PyQuery as pq

from .const import (
    CHALLENGE_REGEX,
    HTTP_TIMEOUT,
    ApiType,
    Page,
    Selector,
    SomfyError,
    LIST_ELEMENTS,
    LIST_ELEMENTS_PRINT,
    LIST_ELEMENTS_ALT,
    LIST_ELEMENTS_NOLANG,
    LIST_ELEMENTS_ALT_NOLANG,
)

from .protexial_api import ProtexialApi
from .protexial_io_api import ProtexialIOApi
from .protexiom_api import ProtexiomApi
from .protexiom_alt_api import ProtexiomAltApi
from .somfy_exception import SomfyException

_LOGGER: logging.Logger = logging.getLogger(__name__)
_PRINTABLE_CHARS = set(string.printable)

# Keep the authentication challenge coordinate visible in DEBUG, but never
# expose the card answer, passwords, alarm codes or session credentials.
_SENSITIVE_PAYLOAD_FIELDS = frozenset({
    "password", "passwd", "pass", "pwd", "key", "code", "pin", "arm_code",
    "alarm_code", "installer_password", "user_code", "secret", "token",
})

_ACCESS_RIGHTS_MESSAGES = {
    "fr": "Droits d'accès insuffisants",
    "de": "Unzureichende Zugriffsrechte",
    "gb": "Insufficient access rights",
    "en": "Insufficient access rights",
    "sp": "Permisos de acceso insuficientes",
    "es": "Permisos de acceso insuficientes",
    "it": "Diritti di accesso insufficienti",
    "nl": "Onvoldoende toegangsrechten",
}


def _fix_mojibake(text: str) -> str:
    """Best-effort fix for accent mojibake, e.g. 'TÃ©l' -> 'Tél'."""
    try:
        # Re-decode as if the text was incorrectly encoded in latin-1
        return text.encode("latin-1").decode("utf-8")
    except Exception:
        return text


class Status:
    """Container for parsed status.xml values."""

    def __init__(self):
        # Zones
        self.zoneA = "off"
        self.zoneB = "off"
        self.zoneC = "off"

        # Default states
        self.battery = "ok"
        self.radio = "ok"
        self.door = "ok"
        self.alarm = "ok"
        self.box = "ok"

        # GSM information
        self.gsm = "gsm connect au reseau"
        self.recgsm = "4"
        self.opegsm = "orange"

        # Camera
        self.camera = "disabled"

    def __getitem__(self, key):
        """Allow dict-like access (status['zoneA'])."""
        return getattr(self, key)

    def __repr__(self):
        """Debug representation."""
        return (
            "Status("
            f"zoneA={self.zoneA!r}, "
            f"zoneB={self.zoneB!r}, "
            f"zoneC={self.zoneC!r}, "
            f"battery={self.battery!r}, "
            f"radio={self.radio!r}, "
            f"door={self.door!r}, "
            f"alarm={self.alarm!r}, "
            f"box={self.box!r}, "
            f"gsm={self.gsm!r}, "
            f"recgsm={self.recgsm!r}, "
            f"opegsm={self.opegsm!r}, "
            f"camera={self.camera!r}"
            ")"
        )

    def __str__(self):
        """Readable dump of the status values."""
        return (
            f"zoneA:{self.zoneA}, "
            f"zoneB:{self.zoneB}, "
            f"zoneC:{self.zoneC}, "
            f"battery:{self.battery}, "
            f"radio:{self.radio}, "
            f"door:{self.door}, "
            f"alarm:{self.alarm}, "
            f"box:{self.box}, "
            f"gsm:{self.gsm}, "
            f"recgsm:{self.recgsm}, "
            f"opegsm:{self.opegsm}, "
            f"camera:{self.camera}"
        )

    def as_dict(self):
        """Return status as a dictionary."""
        return {
            "zoneA": self.zoneA,
            "zoneB": self.zoneB,
            "zoneC": self.zoneC,
            "battery": self.battery,
            "radio": self.radio,
            "door": self.door,
            "alarm": self.alarm,
            "box": self.box,
            "gsm": self.gsm,
            "recgsm": self.recgsm,
            "opegsm": self.opegsm,
            "camera": self.camera,
        }


class SomfyProtexial:
    """Main API client used by the integration to interact with the centrale."""

    def __init__(
        self,
        session: ClientSession,
        url,
        api_type=None,
        username=None,
        password=None,
        codes=None,
        installer_username=None,
        installer_password=None,
    ) -> None:
        """Initialize the client with HTTP session, base URL and credentials."""
        self.url = url
        self.api_type = api_type
        self.username = username
        self.password = password
        self.codes = codes
        self.installer_username = installer_username
        self.installer_password = installer_password
        self._session_lock = asyncio.Lock()
        self.session = session
        self.cookie = None
        self.api = self.load_api(self.api_type)
        # Language prefix used by localized Protexial web pages (/fr/, /de/, ...).
        # It is detected from the centrale itself and never changes the no-prefix
        # Protexiom paths.
        self.language_prefix = "fr"
        self._language_detected = False
        self._last_elements_candidate = None
        # Like Jeedom's phpProtexiom::detectHwVersion(), which probes the
        # centrale's page layout only once (at eqLogic creation/save) and
        # then always re-queries that exact same URL: once a candidate
        # elements page has produced a fully valid parsed list, it is
        # locked in via _elements_page_locked and every later poll goes
        # straight to it - no more re-trying alternate page variants each
        # time. See get_elements() below for why this matters.
        self._elements_page_locked = False

        # Event journal: remember the working URL after the first successful GET.
        # Some firmwares expose /fr/journal.htm, older ones /journal.htm.
        self._journal_page: str | None = None
        # Installer elements page differs across firmware generations. Cache
        # the first working variant so subsequent pause/reactivate commands do
        # not retry a known-missing URL.
        self._installer_elements_candidate = None
        # General installer settings page also differs across firmware families.
        # Cache the first working variant for the time synchronization button.
        self._installer_general_candidate = None
        self._general_settings_cache: dict[str, str] | None = None
        self._general_settings_available_fields: set[str] = set()
        # Last successfully parsed elements list. Used as a fallback when a
        # poll returns an empty/garbled elements page (the same class of
        # Somfy session bug already worked around for status.xml), so a
        # transient bad read doesn't make every door/window sensor flip to
        # "closed". See get_elements() below.
        self._last_good_elements: list[dict] = []

    async def __do_call(
        self,
        method: str,
        page,
        headers: dict | None = None,
        data: dict | None = None,
        retry: bool = True,
        login: bool = True,
        authenticated: bool = True,
    ):
        """Low-level HTTP wrapper handling cookies, error pages and retries."""
        headers = {} if headers is None else dict(headers)

        # Path: accept enum Page or a raw string "/fr/xxx.htm"
        if isinstance(page, str) and page.startswith("/"):
            path = page
        else:
            path = self.api.get_page(page)

        full_path = f"{self.url}{path}"

        try:
            if self.cookie and authenticated:
                _LOGGER.debug("Using cookie: [REDACTED]")
                headers["Cookie"] = self.cookie
            payload = None
            if data is not None:
                headers["Content-Type"] = "application/x-www-form-urlencoded"
                payload = urlencode(data, encoding=self.api.get_encoding())

            async with asyncio.timeout(HTTP_TIMEOUT):
                _LOGGER.debug("Call to: %s", full_path)
                if method == "get":
                    response = await self.session.get(full_path, headers=headers)
                elif method == "post":
                    safe_data = {
                        key: "***" if key.lower() in _SENSITIVE_PAYLOAD_FIELDS else value
                        for key, value in data.items()
                    }
                    _LOGGER.debug("With payload: %s", safe_data)
                    _LOGGER.debug(
                        "With payload (encoded): %s",
                        urlencode(safe_data, encoding=self.api.get_encoding()),
                    )
                    response = await self.session.post(
                        full_path, data=payload, headers=headers
                    )
                else:
                    raise ValueError(f"Unsupported method '{method}'")

            # Response logs (truncate body preview)
            try:
                preview = await response.text(self.api.get_encoding())
            except Exception:
                preview = "<unreadable>"
            _LOGGER.debug("Response path: %s", getattr(response.real_url, "path", "?"))
            _LOGGER.debug(
                "Response headers: %s",
                {
                    key: "[REDACTED]" if key.lower() in ("set-cookie", "cookie") else value
                    for key, value in response.headers.items()
                },
            )
            _LOGGER.debug("Response body (first 500 chars): %s", preview[:500])

            if response.status != 200:
                raise SomfyException(f"Http error ({response.status})")

            # Default page redirection => login may be required
            if (
                getattr(response.real_url, "path", "")
                == self.api.get_page(Page.DEFAULT)
                and retry
            ):
                await self.__login()
                return await self.__do_call(
                    method,
                    page,
                    headers=headers,
                    data=data,
                    retry=False,
                    login=False,
                    authenticated=authenticated,
                )

            # Somfy error page
            if getattr(response.real_url, "path", "") == self.api.get_page(Page.ERROR):
                dom = pq(preview)
                error_el = dom(self.api.get_selector(Selector.ERROR_CODE))
                if not error_el:
                    _LOGGER.error(preview)
                    raise SomfyException("Unknown error")
                code = error_el.text()

                if code == SomfyError.NOT_AUTHORIZED:
                    if not self.cookie and retry:
                        await self.__login()
                        return await self.__do_call(
                            method,
                            page,
                            headers=headers,
                            data=data,
                            retry=False,
                            login=False,
                            authenticated=authenticated,
                        )
                    raise SomfyException(
                        "Command failed: "
                        + _ACCESS_RIGHTS_MESSAGES.get(
                            self.language_prefix, _ACCESS_RIGHTS_MESSAGES["gb"]
                        )
                        + " (0x0903)"
                    )

                if code == SomfyError.SESSION_ALREADY_OPEN:
                    if retry:
                        form = self.api.get_reset_session_payload()
                        await self.__do_call(
                            "post",
                            Page.ERROR,
                            data=form,
                            retry=False,
                            login=False,
                            authenticated=False,
                        )
                        _LOGGER.warning(
                            "Somfy session already open for request: %s %s (code=%s); "
                            "session reset and request retry in progress",
                            method,
                            full_path,
                            code,
                        )
                        self.cookie = None
                        if login:
                            await self.__login()
                        return await self.__do_call(
                            method,
                            page,
                            headers=headers,
                            data=data,
                            retry=False,
                            login=login,
                            authenticated=authenticated,
                        )
                    raise SomfyException("Too many login retries")

                if code in (
                    SomfyError.WRONG_CREDENTIALS,
                    SomfyError.WRONG_CREDENTIALS_ALT,
                    SomfyError.WRONG_CREDENTIALS_2_ALT,
                ):
                    raise SomfyException("Login failed: Wrong credentials")
                if code == SomfyError.MAX_LOGIN_ATTEMPTS:
                    raise SomfyException("Login failed: Max attempt count reached")
                if code == SomfyError.INCORRECT_ACCESS_RIGHTS:
                    _LOGGER.error(
                        "Somfy login refused: incorrect access rights (0x0811)"
                    )
                    raise SomfyException(
                        "Login failed: Incorrect access rights (0x0811)"
                    )
                if code in (
                    SomfyError.WRONG_CODE,
                    SomfyError.WRONG_CODE_ALT,
                ):
                    raise SomfyException("Login failed: Wrong code")
                if code in (
                    SomfyError.UNKNOWN_PARAMETER,
                    SomfyError.UNKNOWN_PARAMETER_ALT,
                ):
                    raise SomfyException("Command failed: Unknown parameter")
                if code == SomfyError.BAD_PARAMETER:
                    raise SomfyException("Command failed: Bad parameter (0x0800)")

                if code == SomfyError.UNEXPECTED_ERROR:
                    raise SomfyException("Unexpected centrale error")
                _LOGGER.error(preview)

                raise SomfyException(f"Command failed: Unknown errorCode: {code}")

            # Normal success
            return response

        except asyncio.TimeoutError as ex:
            _LOGGER.error("Timeout error fetching information from %s - %s", path, ex)
            raise SomfyException(
                f"Timeout error fetching information from {full_path} - {ex}"
            ) from ex
        except ClientError as ex:
            _LOGGER.error("Error fetching information from %s - %s", path, ex)
            raise SomfyException(
                f"Error fetching information from {path} - {ex}"
            ) from ex
        except SomfyException:
            raise
        except Exception as ex:
            _LOGGER.error("Something really wrong happened! - %s", ex)
            raise SomfyException(f"Something really wrong happened! - {ex}") from ex

    def _localized_path(self, path: str) -> str:
        """Return *path* with /fr/ replaced by the detected UI language."""
        if isinstance(path, str) and path.startswith("/fr/"):
            return f"/{self.language_prefix}/{path[4:]}"
        return path

    async def _detect_language_prefix(self) -> str:
        """Detect localized Protexial pages from the root redirect.

        German 2010 firmware redirects / to /de/login.htm. French firmware
        normally redirects to /fr/login.htm. If the root does not reveal a
        language, probe localized login pages with safe GET requests only.
        """
        if self._language_detected:
            return self.language_prefix

        detected = None
        try:
            async with asyncio.timeout(HTTP_TIMEOUT):
                response = await self.session.get(
                    f"{self.url}/", headers={}, allow_redirects=False
                )
            location = response.headers.get("Location", "")
            match = re.search(r"^/([a-zA-Z]{2})/login\.htm(?:[?#].*)?$", location)
            if match:
                detected = match.group(1).lower()
        except (asyncio.TimeoutError, ClientError):
            pass

        if detected is None:
            # Keep this deliberately small and GET-only. French remains first
            # for backwards compatibility; German is the firmware reported in #28.
            for prefix in ("fr", "de", "gb", "en", "it", "sp", "es", "nl", "pt"):
                try:
                    async with asyncio.timeout(HTTP_TIMEOUT):
                        response = await self.session.get(
                            f"{self.url}/{prefix}/login.htm",
                            headers={},
                            allow_redirects=False,
                        )
                    if response.status == 200:
                        detected = prefix
                        break
                except (asyncio.TimeoutError, ClientError):
                    continue

        self.language_prefix = detected or "fr"
        self._language_detected = True
        self.api.set_language_prefix(self.language_prefix)
        _LOGGER.info("Somfy web UI language prefix detected: /%s/", self.language_prefix)
        return self.language_prefix

    async def init(self):
        """Log in at startup, retrying once after transient access-rights errors."""
        await self._detect_language_prefix()
        try:
            await self.__login()
            return
        except SomfyException as err:
            # Some Somfy firmwares can sporadically reject a valid login with
            # error 0x0811 ("Connexion impossible, droit d'accès incorrect").
            # A later manual reload succeeds without any credential change.
            # Treat only this specific startup error as transient: acknowledge
            # the error page when possible, wait briefly, then request a fresh
            # challenge and retry exactly once.
            if "(0x0811)" not in str(err):
                raise

            _LOGGER.warning(
                "Initial Somfy login refused with 0x0811; "
                "resetting the error page and retrying once in 5 seconds"
            )

            self.cookie = None
            try:
                form = self.api.get_reset_session_payload()
                await self.__do_call(
                    "post",
                    Page.ERROR,
                    data=form,
                    retry=False,
                    login=False,
                    authenticated=False,
                )
            except SomfyException as reset_err:
                # The reset is best-effort. The important part is to fetch a
                # fresh login challenge on the second attempt.
                _LOGGER.debug(
                    "Unable to acknowledge Somfy error page before 0x0811 retry: %s",
                    reset_err,
                )

            await asyncio.sleep(5)
            self.cookie = None
            await self.__login()

    async def get_version(self):
        """Return firmware/version string, combining footer year and version page if present."""
        version_string = "Unknown"
        try:
            error_response = await self.__do_call(
                "get", Page.LOGIN, login=False, authenticated=False
            )
            dom = pq(await error_response.text(self.api.get_encoding()))
            footer_element = dom(self.api.get_selector(Selector.FOOTER))
            if footer_element is not None:
                matches = re.search(
                    r"([0-9]{4}) somfy", footer_element.text(), re.IGNORECASE
                )
                if len(matches.groups()) > 0:
                    version_string = matches.group(1)

            if self.api.get_page(Page.VERSION) is not None:
                response = await self.__do_call(
                    "get", Page.VERSION, login=False, authenticated=False
                )
                version = await response.text(self.api.get_encoding())
                version_string += f" ({version.strip()})"
        except Exception as exception:
            _LOGGER.error("Failed to extract version: %s", exception)
        return version_string

    def load_api(self, api_type: ApiType):
        """Create the proper API adapter based on centrale type."""
        if api_type == ApiType.PROTEXIAL:
            return ProtexialApi()
        elif api_type == ApiType.PROTEXIAL_IO:
            return ProtexialIOApi()
        elif api_type == ApiType.PROTEXIOM:
            return ProtexiomApi()
        elif api_type == ApiType.PROTEXIOM_ALT:
            return ProtexiomAltApi()
        elif api_type is not None:
            raise SomfyException(f"Unknown api type: {api_type}")
        return ProtexialApi()

    async def guess_and_set_api_type(self):
        """Try different API flavors until login/version pages match, then set api_type."""
        await self._detect_language_prefix()
        for api_type in [
            ApiType.PROTEXIAL_IO,
            ApiType.PROTEXIAL,
            ApiType.PROTEXIOM,
            ApiType.PROTEXIOM_ALT,
        ]:
            _LOGGER.debug("Trying API detection: %s", api_type)
            self.api = self.load_api(api_type)
            self.api.set_language_prefix(self.language_prefix)
            has_version_page = False
            # Some older systems don't have a version page
            versionPage = self.api.get_page(Page.VERSION)
            if versionPage is not None:
                has_version_page = True
                version_body = await self.do_guess_get(versionPage)

            # Either the system doesn't have a version page, or the page was successfully retrieved
            if not has_version_page or version_body is not None:
                # Now check the login page
                loginPage = self.api.get_page(Page.LOGIN)
                login_body = await self.do_guess_get(loginPage)
                if login_body is not None:
                    # The system has a login page
                    dom = pq(login_body)

                    # PROTEXIOM_ALT uses a broader login challenge selector than
                    # the historical PROTEXIOM API. A classic Protexiom page can
                    # therefore also match the ALT selector.
                    #
                    # Keep PROTEXIOM_ALT as a true fallback: if the classic
                    # Protexiom challenge marker is present and contains a valid
                    # challenge coordinate, do not classify this centrale as ALT.
                    if api_type == ApiType.PROTEXIOM_ALT:
                        classic_api = ProtexiomApi()
                        classic_challenge_element = dom(
                            classic_api.get_selector(Selector.LOGIN_CHALLENGE)
                        )

                        if classic_challenge_element:
                            classic_challenge_text = (
                                classic_challenge_element.text() or ""
                            ).strip()
                            classic_match = re.search(
                                CHALLENGE_REGEX, classic_challenge_text
                            )

                            if classic_match:
                                _LOGGER.debug(
                                    "Skipping PROTEXIOM_ALT detection: "
                                    "classic PROTEXIOM challenge marker found "
                                    "(challenge=%s, raw='%s')",
                                    classic_match.group(0),
                                    classic_challenge_text,
                                )
                                continue

                    challenge_element = dom(
                        self.api.get_selector(Selector.LOGIN_CHALLENGE)
                    )
                    # Check if the challenge element is present
                    if challenge_element is not None:
                        challenge_text = challenge_element.text().strip()

                        match = re.search(CHALLENGE_REGEX, challenge_text)
                        _LOGGER.debug(
                            "API %s raw challenge='%s'",
                            api_type,
                            challenge_text,
                        )
                        if match:
                            challenge = match.group(0)

                            _LOGGER.debug(
                                "Detected API %s with challenge %s",
                                api_type,
                                challenge,
                            )

                            self.api_type = api_type
                            return self.api_type

                        else:
                            _LOGGER.debug(
                                "Challenge not recognized for %s: %s",
                                api_type,
                                challenge_text,
                            )
        raise SomfyException("Couldn't detect the centrale type")

    async def do_guess_get(self, page) -> str:
        """Helper used during API type guessing to fetch a page without full login flow."""
        try:
            async with asyncio.timeout(HTTP_TIMEOUT):
                _LOGGER.debug(f"Guess '{self.url + page}'")
                response = await self.session.get(
                    self.url + page, headers={}, allow_redirects=False
                )

                _LOGGER.debug("Guess response status: %s", response.status)
                _LOGGER.debug("Guess response headers: %s", response.headers)
                _LOGGER.debug("Guess response URL: %s", response.real_url)

            if response.status == 200:
                response_body = await response.text(self.api.get_encoding())
                _LOGGER.debug(
                    f"Guess response: {await response.text(self.api.get_encoding())}"
                )
                return response_body
            elif response.status == 302:
                raise SomfyException("Unavailable, please retry later")
            # Looks like another model
        except asyncio.TimeoutError as exception:
            raise SomfyException(
                f"Timeout error fetching from '{self.url + page}'"
            ) from exception
        except ClientError as exception:
            raise SomfyException(
                f"Error fetching from '{self.url + page}'"
            ) from exception
        except UnicodeDecodeError as exception:
            _LOGGER.error(
                "Incompatible encoding found in '%s' - %s", self.url + page, exception
            )
        except SomfyException:
            raise
        except Exception as exception:
            _LOGGER.error(
                "Something really wrong happened when fetching from '%s' ! - %s",
                self.url + page,
                exception,
            )
        return None

    async def get_challenge(self):
        """Read the login challenge (grid coordinate) from the login page."""
        login_response = await self.__do_call("get", Page.LOGIN, login=False)
        dom = pq(await login_response.text(self.api.get_encoding()))
        challenge_element = dom(self.api.get_selector(Selector.LOGIN_CHALLENGE))

        if not challenge_element:
            raise SomfyException("Challenge not found")

        raw_challenge = challenge_element.text()

        # Extract challenge coordinate (e.g. A1, D5, E2...) even if the page
        # contains additional text such as "Code d'authentification E5".
        match = re.search(CHALLENGE_REGEX, raw_challenge)

        _LOGGER.debug("Raw login challenge: %s", raw_challenge)

        if match:
            challenge = match.group(0)
            _LOGGER.debug("Challenge detected: %s (raw='%s')", challenge, raw_challenge)
            return challenge
        return raw_challenge

        # raise SomfyException(
        #    f"Challenge not recognized (raw value: '{challenge}')"
        # )

    async def __login(self, username=None, password=None, code=None):
        """Perform login and store the session cookie."""
        self.cookie = None
        if code is None:
            challenge = await self.get_challenge()
            code = self.codes[challenge]

        form = self.api.get_login_payload(
            username if username else self.username,
            password if password else self.password,
            code,
        )
        login_response = await self.__do_call(
            "post", Page.LOGIN, data=form, retry=False, login=False
        )
        cookie = login_response.headers.get("SET-COOKIE")
        if cookie:
            self.cookie = cookie.split(";")[0]
        else:
            self.cookie = None

        _LOGGER.debug("Stored cookie: %s", "[REDACTED]" if self.cookie else None)

    def set_credentials(self, username, password, codes):
        self.username = username
        self.password = password
        self.codes = codes

    async def __logout(self):
        """Logout without taking the operation lock (internal use only)."""
        try:
            await self.__do_call("get", Page.LOGOUT, retry=False, login=False)
        finally:
            self.cookie = None

    async def logout(self):
        """Logout and clear session cookie."""
        async with self._session_lock:
            await self.__logout()

    async def get_status(self) -> Status:
        """Fetch and parse status.xml (wrapped with the session-retry safety net).

        Unlike get_elements() and the action commands (arm/disarm/cover/
        light), this call used to go straight to __get_status() with no
        retry: a single slow/timed-out response from the centrale (rare,
        but observed - e.g. an occasional status.xml request taking longer
        than HTTP_TIMEOUT) would propagate straight up to the
        DataUpdateCoordinator as a failure, which Home Assistant surfaces
        by marking every entity "unavailable" for one poll cycle before
        the next scheduled attempt (typically) succeeds on its own.
        Wrapping it in __with_session_retry() closes that gap: a timeout
        or connection error now gets one immediate retry (with a forced
        fresh login, Jeedom-style) before giving up, so an isolated slow
        response is far more likely to be absorbed transparently instead
        of flashing every Somfy entity unavailable.
        """
        page_is_authenticated = self.api.is_page_authenticated(Page.STATUS)
        _LOGGER.debug(
            "AUTH CHECK: Page.STATUS=%s authenticated=%s",
            self.api.get_page(Page.STATUS),
            self.api.is_page_authenticated(Page.STATUS),
        )
        _LOGGER.debug(
            "GET STATUS PARSER auth=%s",
            page_is_authenticated,
        )
        async with self._session_lock:
            return await self.__with_session_retry(
                self.__get_status, page_is_authenticated
            )

    async def __with_session_retry(self, func, *args, **kwargs):
        """Last-resort safety net mirroring Jeedom's
        workaroundSomfySessionTimeoutBug().

        Jeedom's phpProtexiom client wraps pullStatus(), pullElements() and
        doAction() unconditionally: whatever error comes back from the HTTP
        layer, it forces a fresh logout/login and retries the call once.

        __do_call() above already retries internally for a few specific,
        recognized conditions (redirect to the DEFAULT page, the
        NOT_AUTHORIZED/SESSION_ALREADY_OPEN error codes). But anything else
        - an HTTP error status, a timeout, a connection error, or an
        unrecognized Somfy error code - is raised straight away as a
        SomfyException with no retry, unlike the Jeedom reference plugin.

        This wrapper closes that gap: on any SomfyException coming out of
        the wrapped call, force a fresh login and retry the whole operation
        exactly once before giving up.
        """
        try:
            return await func(*args, **kwargs)
        except SomfyException as ex:
            _LOGGER.warning(
                "Request failed (%s); forcing a fresh login and retrying "
                "once (Jeedom-style session recovery)",
                ex,
            )
            try:
                await self.__logout()
            except SomfyException as logout_ex:
                _LOGGER.debug("Logout before retry failed (ignored): %s", logout_ex)
            self.cookie = None
            await self.__login()
            return await func(*args, **kwargs)

    async def __get_status(
        self, page_is_authenticated: bool, _retry_on_empty: bool = True
    ):
        """Fetch and parse status.xml into a Status object.

        Some Protexial/Protexiom firmwares occasionally answer status.xml
        with every field empty (instead of returning an HTTP/login error)
        once a session has been kept open for a while. This is a known
        Somfy firmware bug (also handled by the Jeedom plugin, which checks
        the 'ALARM'/defaut3 tag and forces a fresh login when it is empty).
        We replicate that workaround here: if defaut3 (alarm) comes back
        empty, force a logout/login cycle and retry once.
        """
        status_response = await self.__do_call(
            "get",
            Page.STATUS,
            login=page_is_authenticated,
            authenticated=page_is_authenticated,
        )
        content = await status_response.text(self.api.get_encoding())
        _LOGGER.debug("STATUS XML RECEIVED:\n%s", content)
        response = ET.fromstring(content)
        _LOGGER.debug("XML PARSED OK")
        status = Status()
        _LOGGER.debug("STATUS OBJECT CREATED: %s", status.__dict__)
        for child in response:
            filteredChildText = self.filter_ascii(child.text)
            _LOGGER.debug(
                "XML FIELD: %s=%s",
                child.tag,
                filteredChildText,
            )
            match child.tag:
                case "defaut0":
                    status.battery = filteredChildText
                case "defaut1":
                    status.radio = filteredChildText
                case "defaut2":
                    status.door = filteredChildText
                case "defaut3":
                    status.alarm = filteredChildText
                case "defaut4":
                    status.box = filteredChildText
                case "zone0":
                    status.zoneA = filteredChildText
                case "zone1":
                    status.zoneB = filteredChildText
                case "zone2":
                    status.zoneC = filteredChildText
                case "gsm":
                    status.gsm = filteredChildText
                case "recgsm":
                    status.recgsm = filteredChildText
                case "opegsm":
                    status.opegsm = filteredChildText
                case "camera":
                    status.camera = filteredChildText

        if _retry_on_empty and not status.alarm:
            _LOGGER.warning(
                "Empty status.xml received (known Somfy session bug), "
                "forcing a fresh login and retrying once"
            )
            try:
                await self.__logout()
            except SomfyException as ex:
                _LOGGER.debug("Logout before retry failed (ignored): %s", ex)
            self.cookie = None
            await self.__login()
            page_is_authenticated = self.api.is_page_authenticated(Page.STATUS)
            return await self.__get_status(page_is_authenticated, _retry_on_empty=False)
        _LOGGER.debug(
            "STATUS OBJECT: battery=%s zoneA=%s zoneB=%s gsm=%s",
            status.battery,
            status.zoneA,
            status.zoneB,
            status.gsm,
        )
        _LOGGER.debug("STATUS BEFORE RETURN: %s", status.__dict__)
        return status

    def filter_ascii(self, value) -> str:
        """Keep only printable ASCII (helps with odd encodings) and lowercase the result."""
        if value is None:
            return value
        filtered = "".join(filter(lambda x: x in _PRINTABLE_CHARS, value))
        _LOGGER.debug("Filtered status: '%s'", filtered.lower())
        return filtered.lower()

    async def get_challenge_card(self, username, password, code):
        """Log in and scrape the full authentication card (grid) values, then logout."""
        await self.__login(username, password, code)
        status_response = await self.__do_call("get", Page.CHALLENGE_CARD, login=False)
        dom = pq(await status_response.text(self.api.get_encoding()))
        all_challenge_elements = dom(self.api.get_selector(Selector.CHALLENGE_CARD))
        challenges = {}
        chars = ["A", "B", "C", "D", "E", "F"]
        global_index = 0
        row_index = 0
        col_index = 0
        for elmt in all_challenge_elements:
            col_index = global_index % 6
            if col_index == 0:
                row_index = row_index + 1
            challenges[f"{chars[col_index]}{row_index}"] = elmt.text
            global_index = global_index + 1
        await self.logout()
        return challenges

    async def arm(self, zone):
        """Send ARM for the given zone (wrapped with the session-retry safety net)."""
        async with self._session_lock:
            await self.__with_session_retry(self.__arm, zone)

    async def __arm(self, zone):
        form = self.api.get_arm_payload(zone)
        await self.__do_call("post", Page.PILOTAGE, data=form)

    async def disarm(self):
        """Send DISARM (wrapped with the session-retry safety net)."""
        async with self._session_lock:
            await self.__with_session_retry(self.__disarm)

    async def __disarm(self):
        form = self.api.get_disarm_payload()
        await self.__do_call("post", Page.PILOTAGE, data=form)

    async def turn_light_on(self):
        """Turn light on (wrapped with the session-retry safety net)."""
        async with self._session_lock:
            await self.__with_session_retry(self.__turn_light_on)

    async def __turn_light_on(self):
        form = self.api.get_turn_light_on_payload()
        await self.__do_call("post", Page.PILOTAGE, data=form)

    async def turn_light_off(self):
        """Turn light off (wrapped with the session-retry safety net)."""
        async with self._session_lock:
            await self.__with_session_retry(self.__turn_light_off)

    async def __turn_light_off(self):
        form = self.api.get_turn_light_off_payload()
        await self.__do_call("post", Page.PILOTAGE, data=form)

    async def open_cover(self):
        """Open cover (wrapped with the session-retry safety net)."""
        async with self._session_lock:
            await self.__with_session_retry(self.__open_cover)

    async def __open_cover(self):
        form = self.api.get_open_cover_payload()
        await self.__do_call("post", Page.PILOTAGE, data=form)

    async def close_cover(self):
        """Close cover (wrapped with the session-retry safety net)."""
        async with self._session_lock:
            await self.__with_session_retry(self.__close_cover)

    async def __close_cover(self):
        form = self.api.get_close_cover_payload()
        response = await self.__do_call("post", Page.PILOTAGE, data=form)
        _LOGGER.debug(await response.text(self.api.get_encoding()))

    async def stop_cover(self):
        """Stop cover movement (wrapped with the session-retry safety net)."""
        async with self._session_lock:
            await self.__with_session_retry(self.__stop_cover)

    async def __stop_cover(self):
        form = self.api.get_stop_cover_payload()
        await self.__do_call("post", Page.PILOTAGE, data=form)

    async def __erase_default(self, form: dict):
        """POST an EraseDefault command (reset battery/alarm/link default flags).

        Per the Jeedom phpProtexiom client, these commands are posted to the
        same page as the elements list (u_listelmt.htm), not to u_pilotage.htm.
        The exact path varies with the centrale firmware/hw version:
        with the "/fr/" prefix for Protexial/Protexial-IO style centrales
        (LIST_ELEMENTS_ALT), without it for Protexiom-style ones
        (LIST_ELEMENTS_ALT_NOLANG). We try the candidate most likely to match
        first (based on the last successful get_elements() call, if any),
        then fall back to the other one.
        """
        candidates = [self._localized_path(LIST_ELEMENTS_ALT), LIST_ELEMENTS_ALT_NOLANG]
        if self._last_elements_candidate in candidates:
            candidates = [
                self._last_elements_candidate,
                *[c for c in candidates if c != self._last_elements_candidate],
            ]

        last_exception = None
        for candidate in candidates:
            try:
                await self.__do_call("post", candidate, data=form)
                return
            except SomfyException as ex:
                last_exception = ex
                continue
        if last_exception is not None:
            raise last_exception

    async def reset_battery_err(self):
        """Acknowledge/reset the battery default flag (defaut0)."""
        async with self._session_lock:
            form = self.api.get_reset_battery_err_payload()
            await self.__erase_default(form)

    async def reset_alarm_err(self):
        """Acknowledge/reset the alarm default flag (defaut3)."""
        async with self._session_lock:
            form = self.api.get_reset_alarm_err_payload()
            await self.__erase_default(form)

    async def reset_link_err(self):
        """Acknowledge/reset the radio link default flag (defaut1)."""
        async with self._session_lock:
            form = self.api.get_reset_link_err_payload()
            await self.__erase_default(form)

    def _parse_installer_general_form(self, page_html: str) -> tuple[dict[str, str], set[str]]:
        """Parse the installer general-settings form using browser submission rules."""
        dom = pq(page_html)
        form_dom = dom('form[name="i_reggen"]')
        if not form_dom:
            raise SomfyException("Installer general settings form not found")

        form: dict[str, str] = {}
        available_fields: set[str] = set()

        for input_el in form_dom("input").items():
            name = input_el.attr("name")
            if not name or input_el.attr("disabled") is not None:
                continue
            available_fields.add(name)
            input_type = (input_el.attr("type") or "text").lower()
            if input_type in ("checkbox", "radio"):
                if input_el.attr("checked") is None:
                    continue
                form[name] = input_el.attr("value") or ""
            elif input_type in ("button", "reset", "file", "image"):
                continue
            else:
                form[name] = input_el.attr("value") or ""

        for select_el in form_dom("select").items():
            name = select_el.attr("name")
            if not name or select_el.attr("disabled") is not None:
                continue
            available_fields.add(name)
            options = list(select_el("option").items())
            if not options:
                continue
            selected = next(
                (option for option in options if option.attr("selected") is not None),
                options[0],
            )
            form[name] = selected.attr("value") or selected.text() or ""

        for textarea_el in form_dom("textarea").items():
            name = textarea_el.attr("name")
            if not name or textarea_el.attr("disabled") is not None:
                continue
            available_fields.add(name)
            form[name] = textarea_el.text() or ""

        if "btn_save" not in form:
            raise SomfyException("Installer general settings form is incomplete: btn_save")

        return form, available_fields

    async def _installer_general_operation(
        self, changes: dict[str, str | None] | None = None
    ) -> dict[str, str]:
        """Read or update installer general settings while preserving unrelated fields.

        This method assumes the caller holds _session_lock. GET probing of the two
        known URLs is safe; after a POST is attempted we never retry another URL,
        because the centrale may already have applied the state-changing request.
        """
        if not self.installer_username or not self.installer_password:
            raise SomfyException("Installer credentials are not configured")

        try:
            try:
                await self.__logout()
            except SomfyException as ex:
                _LOGGER.debug("User logout before general settings access failed: %s", ex)
                self.cookie = None

            await self.__login(
                username=self.installer_username,
                password=self.installer_password,
            )

            candidates = [self._localized_path("/fr/i_reggen.htm"), "/i_reggen.htm"]
            if self._installer_general_candidate in candidates:
                candidates.remove(self._installer_general_candidate)
                candidates.insert(0, self._installer_general_candidate)

            last_exception = None
            for candidate in candidates:
                post_attempted = False
                try:
                    response = await self.__do_call(
                        "get", candidate, retry=False, login=False
                    )
                    if getattr(response.real_url, "path", "") == self.api.get_page(
                        Page.DEFAULT
                    ):
                        raise SomfyException(
                            "Installer general settings page redirected to the default page"
                        )

                    page_html = await response.text(self.api.get_encoding())
                    try:
                        form, available_fields = self._parse_installer_general_form(page_html)
                    except SomfyException as ex:
                        raise SomfyException(f"{ex} on {candidate}") from ex

                    self._installer_general_candidate = candidate
                    self._general_settings_cache = dict(form)
                    self._general_settings_available_fields = set(available_fields)

                    if changes is None:
                        return dict(form)

                    unknown = set(changes).difference(available_fields)
                    if unknown:
                        raise SomfyException(
                            "Unsupported installer general setting(s): "
                            + ", ".join(sorted(unknown))
                        )

                    # Apply only the explicitly requested fields. None means an
                    # unchecked checkbox, i.e. omit the field from form submission.
                    for key, value in changes.items():
                        if value is None:
                            form.pop(key, None)
                        else:
                            form[key] = str(value)

                    _LOGGER.debug(
                        "Posting Somfy installer general settings to %s; changed fields: %s",
                        candidate,
                        ", ".join(sorted(changes)),
                    )
                    post_attempted = True
                    post_response = await self.__do_call(
                        "post", candidate, data=form, retry=False, login=False
                    )
                    if getattr(post_response.real_url, "path", "") == self.api.get_page(
                        Page.DEFAULT
                    ):
                        raise SomfyException(
                            "General settings update was redirected to the default page"
                        )

                    # The auto-clock checkbox (update_time) shares this same full-page
                    # form. Preserve its state explicitly and verify it after every
                    # settings write: some centrale firmwares may accept the POST while
                    # silently changing/losing that checkbox state.
                    #
                    # This remains deliberately conservative: the normal path still
                    # performs a single state-changing POST. A corrective POST is made
                    # only after a fresh GET has proved that update_time no longer
                    # matches the state we just submitted, and it is sent only to the
                    # already-confirmed URL (never to a fallback URL).
                    expected_update_time_present = "update_time" in form
                    expected_update_time_value = form.get("update_time", "")

                    verify_response = await self.__do_call(
                        "get", candidate, retry=False, login=False
                    )
                    if getattr(verify_response.real_url, "path", "") == self.api.get_page(
                        Page.DEFAULT
                    ):
                        raise SomfyException(
                            "General settings verification was redirected to the default page"
                        )

                    verify_html = await verify_response.text(self.api.get_encoding())
                    verify_form, verify_available_fields = (
                        self._parse_installer_general_form(verify_html)
                    )
                    actual_update_time_present = "update_time" in verify_form

                    if (
                        "update_time" in available_fields
                        and actual_update_time_present != expected_update_time_present
                    ):
                        _LOGGER.warning(
                            "Somfy general settings changed 'update_time' unexpectedly "
                            "after saving; restoring the previous checkbox state"
                        )

                        # Rebuild from the freshly-read form so every unrelated field is
                        # preserved exactly as the centrale currently exposes it.
                        if expected_update_time_present:
                            verify_form["update_time"] = expected_update_time_value
                        else:
                            verify_form.pop("update_time", None)

                        await asyncio.sleep(1.5)
                        restore_response = await self.__do_call(
                            "post",
                            candidate,
                            data=verify_form,
                            retry=False,
                            login=False,
                        )
                        if getattr(restore_response.real_url, "path", "") == self.api.get_page(
                            Page.DEFAULT
                        ):
                            raise SomfyException(
                                "General settings auto-clock restoration was redirected "
                                "to the default page"
                            )

                        # Verify the corrective save once. Do not loop or blindly retry
                        # state-changing requests on this old embedded web server.
                        final_response = await self.__do_call(
                            "get", candidate, retry=False, login=False
                        )
                        final_html = await final_response.text(self.api.get_encoding())
                        final_form, final_available_fields = (
                            self._parse_installer_general_form(final_html)
                        )
                        if (
                            "update_time" in final_available_fields
                            and ("update_time" in final_form)
                            != expected_update_time_present
                        ):
                            raise SomfyException(
                                "General settings were updated, but the centrale did not "
                                "preserve the 'update_time' state"
                            )

                        verify_form = final_form
                        verify_available_fields = final_available_fields

                    self._general_settings_cache = dict(verify_form)
                    self._general_settings_available_fields = set(
                        verify_available_fields
                    )
                    _LOGGER.info(
                        "Somfy installer general settings updated and verified "
                        "successfully via %s: %s",
                        candidate,
                        ", ".join(sorted(changes)),
                    )
                    return dict(verify_form)

                except SomfyException as ex:
                    last_exception = ex
                    if post_attempted:
                        raise
                    if "Http error (404)" in str(ex) or "form not found" in str(ex):
                        _LOGGER.debug(
                            "Somfy installer general settings candidate %s unavailable: %s",
                            candidate,
                            ex,
                        )
                        continue
                    raise

            if last_exception is not None:
                raise last_exception
            raise SomfyException("Installer general settings page is unavailable")
        finally:
            try:
                await self.__logout()
            except SomfyException as ex:
                _LOGGER.debug("Installer logout after general settings access failed: %s", ex)
                self.cookie = None
            await self.__login()

    async def get_general_settings(self, force: bool = False) -> dict[str, str]:
        """Return installer general settings, using a cache unless a forced read is requested."""
        if not self.installer_username or not self.installer_password:
            raise SomfyException("Installer credentials are not configured")
        if self._general_settings_cache is not None and not force:
            return dict(self._general_settings_cache)

        async with self._session_lock:
            if self._general_settings_cache is not None and not force:
                return dict(self._general_settings_cache)
            return await self._installer_general_operation()

    def general_setting_supported(self, field: str) -> bool:
        """Return whether the last parsed i_reggen form contains the requested field."""
        return field in self._general_settings_available_fields

    async def update_general_settings(
        self, changes: dict[str, str | None]
    ) -> dict[str, str]:
        """Update selected installer settings while preserving every other form value."""
        async with self._session_lock:
            return await self._installer_general_operation(changes)

    async def get_centrale_datetime(self) -> dict[str, str]:
        """Read the date/time currently configured in the Somfy centrale."""
        settings = await self.get_general_settings(force=True)
        required = ("date_dd", "date_mm", "date_yy", "heure_hh", "heure_mm")
        missing = [field for field in required if field not in settings]
        if missing:
            raise SomfyException(
                "Installer general settings page does not expose date/time field(s): "
                + ", ".join(missing)
            )

        return {field: str(settings[field]).strip() for field in required}

    async def sync_centrale_datetime(self, current_datetime) -> None:
        """Synchronize the centrale date/time with Home Assistant local time."""
        changes = {
            "date_dd": f"{current_datetime.day:02d}",
            "date_mm": f"{current_datetime.month:02d}",
            "date_yy": str(current_datetime.year),
            "heure_hh": f"{current_datetime.hour:02d}",
            "heure_mm": f"{current_datetime.minute:02d}",
        }
        await self.update_general_settings(changes)

    async def set_element_active(self, element_id: str, active: bool) -> None:
        """Temporarily use the installer account to toggle an element.

        The Somfy installer page exposes a toggle-only POST. The caller must
        therefore invoke this method only when the requested state differs
        from the state currently reported by the user elements page.
        """
        if not self.installer_username or not self.installer_password:
            raise SomfyException("Installer credentials are not configured")

        async with self._session_lock:
            _LOGGER.info(
                "Changing Somfy element %s to %s using a temporary installer session",
                element_id,
                "active" if active else "paused",
            )

            # The centrale accepts only one session at a time. Close the normal
            # user session, perform the installer-only action, then always try
            # to restore the normal user session, even if the toggle fails.
            try:
                try:
                    await self.__logout()
                except SomfyException as ex:
                    _LOGGER.debug("User logout before installer action failed: %s", ex)
                    self.cookie = None

                await self.__login(
                    username=self.installer_username,
                    password=self.installer_password,
                )

                # Installer page location differs between firmware families:
                # newer/french-localized centrales use /fr/i_listelmt.htm while
                # older ones commonly use /i_listelmt.htm.
                #
                # Known form variants:
                #   /fr/i_listelmt.htm -> elt_preload_2 / apply_2
                #   /i_listelmt.htm    -> elt_preload   / apply
                #
                # Do not rely on api_type alone: some old Protexiom centrales
                # can be detected as PROTEXIOM rather than PROTEXIOM_ALT.
                primary = self.api.get_page(Page.INSTALLER_ELEMENTS)
                localized_installer = self._localized_path("/fr/i_listelmt.htm")
                alternate = (
                    "/i_listelmt.htm"
                    if primary == localized_installer
                    else localized_installer
                )
                candidates = [primary, alternate]
                if self._installer_elements_candidate in candidates:
                    candidates.remove(self._installer_elements_candidate)
                    candidates.insert(0, self._installer_elements_candidate)

                response = None
                last_exception = None
                for index, candidate in enumerate(candidates):
                    # Select a safe default payload from the URL ACTUALLY used.
                    # This is important when the first URL 404s and we fall back
                    # to the other firmware variant.
                    use_legacy_form = candidate == "/i_listelmt.htm"

                    # Extra safety: inspect the installer page before the
                    # state-changing POST and detect the actual field names.
                    try:
                        inspect_response = await self.__do_call(
                            "get",
                            candidate,
                            retry=False,
                            login=False,
                        )
                        inspect_html = await inspect_response.text(
                            self.api.get_encoding()
                        )

                        has_legacy_fields = bool(
                            re.search(
                                r'name=["\']elt_preload["\']',
                                inspect_html,
                                re.IGNORECASE,
                            )
                            and re.search(
                                r'name=["\']apply["\']',
                                inspect_html,
                                re.IGNORECASE,
                            )
                        )
                        has_new_fields = bool(
                            re.search(
                                r'name=["\']elt_preload_2["\']',
                                inspect_html,
                                re.IGNORECASE,
                            )
                            and re.search(
                                r'name=["\']apply_2["\']',
                                inspect_html,
                                re.IGNORECASE,
                            )
                        )

                        if has_legacy_fields:
                            use_legacy_form = True
                        elif has_new_fields:
                            use_legacy_form = False

                        _LOGGER.debug(
                            "Somfy installer form detected on %s: %s",
                            candidate,
                            "legacy (elt_preload/apply)"
                            if use_legacy_form
                            else "new (elt_preload_2/apply_2)",
                        )
                    except SomfyException as inspect_ex:
                        _LOGGER.debug(
                            "Unable to inspect Somfy installer form on %s; "
                            "using URL-based payload fallback: %s",
                            candidate,
                            inspect_ex,
                        )

                    if use_legacy_form:
                        form = {
                            "elt_preload": str(element_id),
                            "toggle": "",
                            "apply": "",
                        }
                    else:
                        form = {
                            "elt_preload_2": str(element_id),
                            "toggle": "",
                            "apply_2": "",
                        }

                    try:
                        response = await self.__do_call(
                            "post",
                            candidate,
                            data=form,
                            retry=False,
                            login=False,
                        )
                        self._installer_elements_candidate = candidate
                        if index > 0:
                            _LOGGER.info(
                                "Somfy installer elements fallback URL selected: %s",
                                candidate,
                            )
                        break
                    except SomfyException as ex:
                        last_exception = ex
                        if str(ex) != "Http error (404)" or index == len(candidates) - 1:
                            raise
                        _LOGGER.debug(
                            "Somfy installer elements page %s returned 404; trying %s",
                            candidate,
                            candidates[index + 1],
                        )

                if response is None:
                    if last_exception is not None:
                        raise last_exception
                    raise SomfyException("Installer elements page is unavailable")

                if getattr(response.real_url, "path", "") == self.api.get_page(
                    Page.DEFAULT
                ):
                    raise SomfyException(
                        "Installer action was redirected to the default page"
                    )
            finally:
                try:
                    await self.__logout()
                except SomfyException as ex:
                    _LOGGER.debug("Installer logout failed: %s", ex)
                    self.cookie = None

                # Restore Home Assistant's normal user session. If this fails,
                # propagate the error so HA reports the command as failed.
                await self.__login()

    async def get_event_journal(self, limit: int = 10) -> list[dict]:
        """Return the most recent events from the user event journal.

        The journal is read-only. Newer/FR firmwares normally expose
        ``/fr/journal.htm`` while older firmwares can expose ``/journal.htm``.
        The alternate URL is tried only after an HTTP 404 and the working URL
        is then cached for the rest of the session.
        """
        async with self._session_lock:
            return await self.__with_session_retry(
                self.__get_event_journal_with_read_retry, limit
            )

    async def __get_event_journal_with_read_retry(
        self, limit: int
    ) -> list[dict]:
        """Retry one transient journal read without changing the login session."""
        for attempt in range(2):
            try:
                return await self.__get_event_journal(limit)
            except SomfyException as err:
                message = str(err)
                transient = (
                    message.startswith("Incomplete event journal")
                    or message.startswith("Unable to parse event journal field:")
                    or message.startswith("Unable to decode event journal field:")
                    or "Connection closed" in message
                )
                # A dropped connection may invalidate the Somfy session.
                # Let the existing outer recovery perform a fresh login rather
                # than retrying with a potentially invalid session.
                if (
                    message.startswith("Event journal response read failed:")
                    or message.startswith("Error fetching information from")
                ):
                    raise
                if not transient or attempt:
                    raise
                _LOGGER.debug(
                    "Transient Somfy event journal read failure (%s); "
                    "retrying GET once with the existing session",
                    message,
                )
                await asyncio.sleep(1)

    async def __get_event_journal(self, limit: int = 10) -> list[dict]:
        """Fetch and parse the first event-journal page."""
        limit = max(1, min(int(limit), 50))

        candidates: list[str] = []
        if self._journal_page:
            candidates.append(self._journal_page)
        for candidate in (self._localized_path("/fr/journal.htm"), "/journal.htm"):
            if candidate not in candidates:
                candidates.append(candidate)

        response = None
        working_page = None
        last_404 = None

        for candidate in candidates:
            try:
                response = await self.__do_call("get", candidate)
                working_page = candidate
                break
            except SomfyException as err:
                # GET is read-only, but keep fallback deliberately narrow:
                # only a missing page (404) justifies trying the other URL.
                if "Http error (404)" in str(err):
                    last_404 = err
                    continue
                raise

        if response is None or working_page is None:
            if last_404 is not None:
                raise last_404
            raise SomfyException("Event journal page not available")

        self._journal_page = working_page
        try:
            body = await response.text(self.api.get_encoding())
        except (ClientError, asyncio.TimeoutError) as err:
            raise SomfyException(
                f"Event journal response read failed: {type(err).__name__}"
            ) from err

        # A complete Somfy journal page ends in </html>. Never accept
        # partially delivered arrays as a valid journal snapshot.
        if not re.search(r"</html>\s*$", body, flags=re.IGNORECASE):
            _LOGGER.debug(
                "Incomplete Somfy event journal: body_length=%d, "
                "html_end_present=False, eventcode_declaration_present=%s",
                len(body),
                bool(re.search(r"var\s+eventcode\s*=", body)),
            )
            raise SomfyException("Incomplete event journal HTML response")

        def _read_js_array(name: str) -> list[str]:
            match = re.search(
                rf"var\s+{re.escape(name)}\s*=\s*(\[.*?\])\s*;",
                body,
                flags=re.DOTALL,
            )
            if not match:
                _LOGGER.debug(
                    "Somfy event journal field missing: field=%s, body_length=%d, "
                    "html_end_present=True",
                    name,
                    len(body),
                )
                raise SomfyException(
                    f"Unable to parse event journal field: {name}"
                )
            try:
                values = json.loads(match.group(1))
            except (json.JSONDecodeError, TypeError) as err:
                raise SomfyException(
                    f"Unable to decode event journal field: {name}"
                ) from err
            if not isinstance(values, list):
                raise SomfyException(
                    f"Unexpected event journal field type: {name}"
                )
            return [str(value) for value in values]

        dates = _read_js_array("eventdate")
        times = _read_js_array("eventtime")
        names = _read_js_array("eventname")
        places = _read_js_array("eventplace")
        codes = _read_js_array("eventcode")

        count = min(limit, len(dates), len(times), len(names), len(places), len(codes))
        events = []
        for index in range(count):
            code = codes[index].strip()
            if code.startswith("(") and code.endswith(")"):
                code = code[1:-1]
            events.append(
                {
                    "date": _fix_mojibake(dates[index].strip()),
                    "time": _fix_mojibake(times[index].strip()),
                    "event": _fix_mojibake(names[index].strip()),
                    "element": _fix_mojibake(places[index].strip()),
                    "code": _fix_mojibake(code),
                }
            )

        _LOGGER.debug(
            "Event journal: read %d event(s) from %s",
            len(events),
            working_page,
        )
        return events

    async def get_elements(self) -> list[dict]:
        """Fetch and parse the elements page (wrapped with the session-retry safety net)."""
        async with self._session_lock:
            return await self.__with_session_retry(self.__get_elements)

    async def __get_elements(self) -> list[dict]:
        _LOGGER.debug("ENTER get_elements()")
        """Fetch and parse the elements page, returning a normalized list of dicts.

        Mirrors the Jeedom reference plugin (phpProtexiom::detectHwVersion()):
        the page variant is detected only once, then every later poll goes
        straight back to that same page - it is never re-guessed. This
        matters because the previous behaviour (re-trying a priority-ordered
        list of 5 page variants on every poll, remembering only the last one
        that happened to answer) is what caused door/window sensors to flap:
        LIST_ELEMENTS ("u_plistelmt.htm", a "print"-style page) was tried
        first and doesn't reliably reflect the live state on this firmware,
        and a single transient hiccup on the locked-in page was enough to
        silently fall through to it, producing an alternating stale/live
        read on the very next poll. Jeedom has always relied on
        "u_listelmt.htm" (LIST_ELEMENTS_ALT here) instead, so that is now
        tried first during detection too.
        """
        if self._elements_page_locked and self._last_elements_candidate is not None:
            # Page variant already detected for this session: don't probe
            # any alternate candidate, just like Jeedom never re-probes
            # detectHwVersion() once HwVersion is set.
            candidates = [self._last_elements_candidate]
        else:
            candidates = [
                self._localized_path(LIST_ELEMENTS_ALT),
                LIST_ELEMENTS_ALT_NOLANG,
                self._localized_path(LIST_ELEMENTS),
                LIST_ELEMENTS_NOLANG,
                self._localized_path(LIST_ELEMENTS_PRINT),
            ]

        html = None
        found_candidate = None
        for candidate in candidates:
            try:
                resp = await self.__do_call("get", candidate)
                raw = await resp.read()

                # Try several encodings
                html = None
                for enc in (
                    "utf-8",
                    "windows-1252",
                    "latin-1",
                    (self.api.get_encoding() or "latin-1"),
                ):
                    try:
                        html = raw.decode(enc)
                        break
                    except Exception:
                        continue

                # Fallback if nothing worked
                if html is None:
                    html = raw.decode("utf-8", errors="ignore")

                found_candidate = candidate
                break  # success → exit loop

            except Exception:
                continue

        if html is None:
            # Known Somfy session bug (same class as the empty status.xml
            # case): no candidate page could be fetched/decoded at all.
            # Keep the previous known-good list instead of returning []
            # (which would make every door/window sensor report "closed").
            # Note: when the page is already locked in, we do NOT fall back
            # to a different page variant here - that fallback is exactly
            # what used to cause the flapping. We just wait for the next
            # poll and retry the same locked page.
            _LOGGER.warning(
                "%s elements page received (known Somfy session bug), "
                "keeping the last known door/window states",
                "Locked" if self._elements_page_locked else "Empty",
            )
            return self._last_good_elements

        # Parse JS arrays
        def extract_array(name: str) -> list[str]:
            """Extract the JS array content and return a list of strings (mojibake-fixed)."""
            m = re.search(rf"var\s+{name}\s*=\s*\[(.*?)\];", html, re.S | re.I)
            if not m:
                return []
            raw_arr = m.group(1)
            parts = [p.strip() for p in raw_arr.split(",")]
            vals = [p.strip().strip('"').strip("'") for p in parts]
            return [_fix_mojibake(v) for v in vals]

        item_label = extract_array("item_label")
        elt_name = extract_array("elt_name")
        elt_code = extract_array("elt_code")
        elt_pile = extract_array("elt_pile")
        elt_onde = extract_array("elt_onde")
        elt_porte = extract_array("elt_porte")
        elt_zone = extract_array("elt_zone")
        elt_as = extract_array("elt_as")
        elt_maison = extract_array("elt_maison")
        item_pause = extract_array("item_pause")

        n = min(len(item_label), len(elt_name), len(elt_code))

        # Defensive validation, mirroring the Jeedom reference client
        # (phpProtexiom.class.php::pullElements(), which rejects the read
        # entirely - without touching previously stored data - if no
        # element is found or if any parsed array's length doesn't match).
        # Here: if nothing was parsed, or the door/window flags are missing
        # while we do have a previous known-good list, this is the same
        # transient session-bug pattern as the empty status.xml case - keep
        # the last known-good elements instead of wiping out every
        # door/window sensor's state.
        if n == 0 or (len(elt_porte) == 0 and self._last_good_elements):
            _LOGGER.warning(
                "%s/incomplete elements page received (known Somfy "
                "session bug), keeping the last known door/window states",
                "Locked elements page returned empty" if self._elements_page_locked else "Empty",
            )
            return self._last_good_elements

        elements: list[dict] = []
        for i in range(n):
            comm = elt_onde[i] if i < len(elt_onde) else "itemhidden"

            el = {
                "label": _fix_mojibake(item_label[i]),
                "name": _fix_mojibake(elt_name[i]),
                "code": elt_code[i],
                "battery": elt_pile[i] if i < len(elt_pile) else "",
                "comm": comm,
                "door": elt_porte[i] if i < len(elt_porte) else "",
                "zone": _fix_mojibake(elt_zone[i]) if i < len(elt_zone) else "",
                "tamper": elt_as[i] if i < len(elt_as) else "",
                "house": elt_maison[i] if i < len(elt_maison) else "",
                "pause": item_pause[i] if i < len(item_pause) else "",
            }
            _LOGGER.debug("EXIT get_elements(): %s", elements)
            elements.append(el)

        # _LOGGER.debug("Extracted elements (count=%d): %s", len(elements), elements[:3])

        # This is a fully valid, successfully parsed read: lock this page
        # variant in for the rest of the session (Jeedom-style one-shot
        # detection) so future polls go straight to it instead of
        # re-testing alternate candidates.
        if found_candidate is not None:
            if not self._elements_page_locked:
                _LOGGER.info(
                    "Elements page detected and locked in for this "
                    "session: %s (won't be re-probed until the "
                    "integration reloads/restarts)",
                    found_candidate,
                )
            self._elements_page_locked = True
            self._last_elements_candidate = found_candidate

        self._last_good_elements = elements
        return elements
