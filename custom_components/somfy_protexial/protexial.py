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

from .const import CHALLENGE_REGEX, HTTP_TIMEOUT, ApiType, Page, Selector, SomfyError, LIST_ELEMENTS, LIST_ELEMENTS_PRINT, LIST_ELEMENTS_ALT
from .protexial_api import ProtexialApi
from .protexial_io_api import ProtexialIOApi
from .protexiom_api import ProtexiomApi
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

    zoneA = "off"
    zoneB = "off"
    zoneC = "off"
    battery = "ok"
    radio = "ok"
    door = "ok"
    alarm = "ok"
    box = "ok"
    gsm = "gsm connect au rseau"
    recgsm = "4"
    opegsm = "orange"
    camera = "disabled"

    def __getitem__(self, key):
        """Allow dict-like access (status['zoneA'])."""
        return getattr(self, key)

    def __str__(self):
        """Readable dump of the status values."""
        return f"zoneA:{self.zoneA}, zoneB:{self.zoneB}, zoneC:{self.zoneC}, battery:{self.battery}, radio:{self.radio}, door:{self.door}, alarm:{self.alarm}, box:{self.box}, gsm:{self.gsm}, recgsm:{self.recgsm}, opegsm:{self.opegsm}, camera:{self.camera}"


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
    ) -> None:
        """Initialize the client with HTTP session, base URL and credentials."""
        self.url = url
        self.api_type = api_type
        self.username = username
        self.password = password
        self.codes = codes
        self.session = session
        self.cookie = None
        self.api = self.load_api(self.api_type)

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
                    response = await self.session.post(full_path, data=payload, headers=headers)
                else:
                    raise ValueError(f"Unsupported method '{method}'")

            # Response logs (truncate body preview)
            try:
                preview = await response.text(self.api.get_encoding())
            except Exception:
                preview = "<unreadable>"
            _LOGGER.debug("Response path: %s", getattr(
                response.real_url, "path", "?"))
            _LOGGER.debug("Response headers: %s", response.headers)
            _LOGGER.debug("Response body (first 500 chars): %s", preview[:500])

            if response.status != 200:
                raise SomfyException(f"Http error ({response.status})")

            # Default page redirection => login may be required
            if getattr(response.real_url, "path", "") == self.api.get_page(Page.DEFAULT) and retry:
                await self.__login()
                return await self.__do_call(
                    method, page, headers=headers, data=data,
                    retry=False, login=False, authenticated=authenticated
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
                        method, page, headers=headers, data=data,
                        retry=False, login=False, authenticated=authenticated
                    )

                if code == SomfyError.SESSION_ALREADY_OPEN:
                    if retry:
                        form = self.api.get_reset_session_payload()
                        await self.__do_call(
                            "post", Page.ERROR, data=form,
                            retry=False, login=False, authenticated=False
                        )
                        self.cookie = None
                        if login:
                            await self.__login()
                        return await self.__do_call(
                            method, page, headers=headers, data=data,
                            retry=False, login=login, authenticated=authenticated
                        )
                    raise SomfyException("Too many login retries")

                if code == SomfyError.WRONG_CREDENTIALS:
                    raise SomfyException("Login failed: Wrong credentials")
                if code == SomfyError.MAX_LOGIN_ATTEMPS:
                    raise SomfyException(
                        "Login failed: Max attempt count reached")
                if code == SomfyError.WRONG_CODE:
                    raise SomfyException("Login failed: Wrong code")
                if code == SomfyError.UNKNOWN_PARAMETER:
                    raise SomfyException("Command failed: Unknown parameter")

                _LOGGER.error(preview)
                raise SomfyException(
                    f"Command failed: Unknown errorCode: {code}")

            # Normal success
            return response

        except asyncio.TimeoutError as ex:
            _LOGGER.error(
                "Timeout error fetching information from %s - %s", path, ex)
            raise SomfyException(
                f"Timeout error fetching information from {full_path} - {ex}") from ex
        except ClientError as ex:
            _LOGGER.error("Error fetching information from %s - %s", path, ex)
            raise SomfyException(
                f"Error fetching information from {path} - {ex}") from ex
        except SomfyException:
            raise
        except Exception as ex:
            _LOGGER.error("Something really wrong happened! - %s", ex)
            raise SomfyException(
                f"Something really wrong happened! - {ex}") from ex

    async def init(self):
        """Log in once at startup."""
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
        elif api_type is not None:
            raise SomfyException(f"Unknown api type: {type}")

    async def guess_and_set_api_type(self):
        """Try different API flavors until login/version pages match, then set api_type."""
        for api_type in [ApiType.PROTEXIAL_IO, ApiType.PROTEXIAL, ApiType.PROTEXIOM]:
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
                    challenge_element = dom(
                        self.api.get_selector(Selector.LOGIN_CHALLENGE)
                    )
                    # Check if the challenge element is present
                    if challenge_element is not None:
                        challenge = challenge_element.text()
                        # Check that the challenge element looks fine
                        if re.match(CHALLENGE_REGEX, challenge):
                            self.api_type = api_type
                            return self.api_type
                        else:
                            _LOGGER.debug(
                                f"Challenge not recognized: {challenge}")
        raise SomfyException("Couldn't detect the centrale type")

    async def do_guess_get(self, page) -> str:
        """Helper used during API type guessing to fetch a page without full login flow."""
        try:
            async with asyncio.timeout(HTTP_TIMEOUT):
                _LOGGER.debug(f"Guess '{self.url + page}'")
                response = await self.session.get(
                    self.url + page, headers={}, allow_redirects=False
                )
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
        challenge_element = dom(
            self.api.get_selector(Selector.LOGIN_CHALLENGE))
        if challenge_element:
            return challenge_element.text()
        else:
            raise SomfyException("Challenge not found")

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
        self.cookie = login_response.headers.get("SET-COOKIE")

    async def logout(self):
        """Logout and clear session cookie."""
        await self.__do_call("get", Page.LOGOUT, retry=False, login=False)
        self.cookie = None

    async def get_status(self):
        """Fetch and parse status.xml into a Status object."""
        status_response = await self.__do_call(
            "get", Page.STATUS, login=False, authenticated=False
        )
        content = await status_response.text(self.api.get_encoding())
        response = ET.fromstring(content)
        status = Status()
        for child in response:
            filteredChildText = self.filter_ascii(child.text)
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
        all_challenge_elements = dom(
            self.api.get_selector(Selector.CHALLENGE_CARD))
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
        """Send ARM for the given zone."""
        form = self.api.get_arm_payload(zone)
        await self.__do_call("post", Page.PILOTAGE, data=form)

    async def disarm(self):
        """Send DISARM."""
        form = self.api.get_disarm_payload()
        await self.__do_call("post", Page.PILOTAGE, data=form)

    async def turn_light_on(self):
        """Turn light on."""
        form = self.api.get_turn_light_on_payload()
        await self.__do_call("post", Page.PILOTAGE, data=form)

    async def turn_light_off(self):
        """Turn light off."""
        form = self.api.get_turn_light_off_payload()
        await self.__do_call("post", Page.PILOTAGE, data=form)

    async def open_cover(self):
        """Open cover."""
        form = self.api.get_open_cover_payload()
        await self.__do_call("post", Page.PILOTAGE, data=form)

    async def close_cover(self):
        """Close cover."""
        form = self.api.get_close_cover_payload()
        response = await self.__do_call("post", Page.PILOTAGE, data=form)
        print(await response.text(self.api.get_encoding()))

    async def stop_cover(self):
        """Stop cover movement."""
        form = self.api.get_stop_cover_payload()
        await self.__do_call("post", Page.PILOTAGE, data=form)

    # protexial_api.py

    def get_page(self, page):
        """Local page mapping helper for the element list pages."""
        mapping = {
            Page.LIST_ELEMENTS: "/fr/u_plistelmt.htm",
            Page.LIST_ELEMENTS_PRINT: "/fr/p_ulistelem.htm",
            Page.LIST_ELEMENTS_ALT: "/fr/u_listelmt.htm",
        }
        return mapping.get(page, page.value if hasattr(page, "value") else page)

    async def get_elements(self) -> list[dict]:
        """Fetch and parse the elements page, returning a normalized list of dicts."""
        candidates = [LIST_ELEMENTS, LIST_ELEMENTS_ALT, LIST_ELEMENTS_PRINT]

        html = None
        for candidate in candidates:
            try:
                resp = await self.__do_call("get", candidate)
                raw = await resp.read()

                # Try several encodings
                html = None
                for enc in ("utf-8", "windows-1252", "latin-1", (self.api.get_encoding() or "latin-1")):
                    try:
                        html = raw.decode(enc)
                        break
                    except Exception:
                        continue

                # Fallback if nothing worked
                if html is None:
                    html = raw.decode("utf-8", errors="ignore")

                # _LOGGER.debug("Elements page used: %s", candidate)
                break  # success → exit loop

            except Exception:
                # _LOGGER.debug("Failed attempt %s", candidate)
                continue

        if html is None:
            # _LOGGER.debug("Could not find a valid elements page among: %s", candidates)
            return []

        # Parse JS arrays
        def extract_array(name: str) -> list[str]:
            """Extract the JS array content and return a list of strings (mojibake-fixed)."""
            m = re.search(rf'var\s+{name}\s*=\s*\[(.*?)\];', html, re.S | re.I)
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
        elements: list[dict] = []
        for i in range(n):
            comm = elt_onde[i] if i < len(elt_onde) else "itemhidden"

            el = {
                "label":   _fix_mojibake(item_label[i]),
                "name":    _fix_mojibake(elt_name[i]),
                "code":    elt_code[i],
                "battery": elt_pile[i] if i < len(elt_pile) else "",
                "comm":    comm,
                "door":    elt_porte[i] if i < len(elt_porte) else "",
                "zone":    _fix_mojibake(elt_zone[i]) if i < len(elt_zone) else "",
                "tamper":  elt_as[i] if i < len(elt_as) else "",
                "house":   elt_maison[i] if i < len(elt_maison) else "",
                "pause":   item_pause[i] if i < len(item_pause) else "",
            }
            elements.append(el)

        # _LOGGER.debug("Extracted elements (count=%d): %s", len(elements), elements[:3])
        return elements
