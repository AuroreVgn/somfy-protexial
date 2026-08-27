import asyncio
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
        self._last_elements_candidate = None
        # Like Jeedom's phpProtexiom::detectHwVersion(), which probes the
        # centrale's page layout only once (at eqLogic creation/save) and
        # then always re-queries that exact same URL: once a candidate
        # elements page has produced a fully valid parsed list, it is
        # locked in via _elements_page_locked and every later poll goes
        # straight to it - no more re-trying alternate page variants each
        # time. See get_elements() below for why this matters.
        self._elements_page_locked = False
        # Installer elements page differs across firmware generations. Cache
        # the first working variant so subsequent pause/reactivate commands do
        # not retry a known-missing URL.
        self._installer_elements_candidate = None
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
                _LOGGER.debug("Using cookie: %s", self.cookie)
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
                    _LOGGER.debug("With payload: %s", data)
                    _LOGGER.debug("With payload (encoded): %s", payload)
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
            _LOGGER.debug("Response headers: %s", response.headers)
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

                if code == SomfyError.NOT_AUTHORIZED and not self.cookie and retry:
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
                        _LOGGER.error(
                            "Somfy ERROR received for request: %s %s (code=%s)",
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
                if code == SomfyError.UNKNOWN_PARAMETER:
                    raise SomfyException("Command failed: Unknown parameter")

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

    async def init(self):
        """Log in at startup, retrying once after transient access-rights errors."""
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
        for api_type in [
            ApiType.PROTEXIAL_IO,
            ApiType.PROTEXIAL,
            ApiType.PROTEXIOM,
            ApiType.PROTEXIOM_ALT,
        ]:
            _LOGGER.debug("Trying API detection: %s", api_type)
            self.api = self.load_api(api_type)
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

        _LOGGER.debug("Stored cookie: %s", self.cookie)

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
        candidates = [LIST_ELEMENTS_ALT, LIST_ELEMENTS_ALT_NOLANG]
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
                alternate = (
                    "/i_listelmt.htm"
                    if primary == "/fr/i_listelmt.htm"
                    else "/fr/i_listelmt.htm"
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
                LIST_ELEMENTS_ALT,
                LIST_ELEMENTS_ALT_NOLANG,
                LIST_ELEMENTS,
                LIST_ELEMENTS_NOLANG,
                LIST_ELEMENTS_PRINT,
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
