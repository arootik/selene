# MIT License
#
# Copyright (c) 2015-2023 Iakiv Kramarenko
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from __future__ import annotations

import atexit
import inspect
import itertools
import os
import time
import typing
import warnings
from typing import Callable, Optional, Any

from selenium.webdriver.common.options import BaseOptions
from selenium.webdriver.remote.command import Command

from selene.common import fp, helpers
from selene.common.data_structures import persistent
from selene.common.fp import F, pipe, thread
from selene.common.helpers import on_error_return_false

from selene.core.exceptions import TimeoutException
from selenium.webdriver.remote.webdriver import WebDriver

from selene.core.wait import Wait, E


# TODO: consider moving to support.*
#       like support._loging.wait_with
def _build_local_driver_by_name_or_remote_by_url_and_options(
    config: Config,
) -> WebDriver:
    from selenium.webdriver import (
        ChromeOptions,
        EdgeOptions,
        Chrome,
        Firefox,
        Edge,
    )

    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.firefox.service import Service as FirefoxService
    from selenium.webdriver.edge.service import Service as EdgeService  # type: ignore

    from webdriver_manager.chrome import ChromeDriverManager  # type: ignore
    from webdriver_manager.firefox import GeckoDriverManager  # type: ignore
    from webdriver_manager.microsoft import EdgeChromiumDriverManager  # type: ignore

    from webdriver_manager.core.utils import ChromeType  # type: ignore

    def install_and_build_chrome():
        if config.driver_options:
            if isinstance(config.driver_options, ChromeOptions):
                return Chrome(
                    service=ChromeService(
                        ChromeDriverManager(
                            chrome_type=ChromeType.GOOGLE
                        ).install()
                    ),
                    options=config.driver_options,
                )
            else:
                raise ValueError(
                    f'Default config.build_driver_strategy («driver factory»), '
                    f'if config.name is set to "chrome", – '
                    f'expects only instance of ChromeOptions or None in config.driver_options,'
                    f'but got: {config.driver_options}'
                )
        else:
            return Chrome(
                service=ChromeService(
                    ChromeDriverManager(
                        chrome_type=ChromeType.GOOGLE
                    ).install()
                )
            )

    def install_and_build_firefox():
        return (
            Firefox(
                service=FirefoxService(GeckoDriverManager().install()),
                options=config.driver_options,
            )
            if config.driver_options
            else Firefox(
                service=FirefoxService(GeckoDriverManager().install())
            )
        )

    def install_and_build_edge():
        if config.driver_options:
            if isinstance(config.driver_options, EdgeOptions):
                return Edge(
                    service=EdgeService(EdgeChromiumDriverManager().install()),
                    options=config.driver_options,
                )
            else:
                raise ValueError(
                    f'Default config.build_driver_strategy, '
                    f'if config.name is set to "edge", – '
                    f'expects only instance of EdgeOptions or None in config.driver_options,'
                    f'but got: {config.driver_options}'
                )
        else:
            return Edge(
                service=EdgeService(EdgeChromiumDriverManager().install())
            )

    def build_remote_driver():
        from selenium.webdriver import Remote

        # TODO: consider guessing browserstack remote url
        #       if noticed 'bstack:options' in config.driver_options

        return Remote(
            command_executor=config.driver_remote_url,
            options=config.driver_options,
        )

    def build_appium_driver():
        try:
            from appium import webdriver
        except ImportError as error:
            raise ImportError(
                'Appium-Python-Client is not installed, '
                'run `pip install Appium-Python-Client`,'
                'or add and install dependency '
                'with your favorite dependency manager like poetry: '
                '`poetry add Appium-Python-Client`'
            ) from error

        # TODO: consider to add more smart guessing of options if not set...
        #       like if driver_name is set to 'appium'
        #       and driver_options is not set
        #       and the base_url is set to url of some web app
        #       then build appium driver options
        #       to run web test on mobile browser
        #       else if base_url is set to app path or url,
        #       parse app type and build corresponding appium driver options
        #       ...
        #       TODO: should we even rename base_url to app_url
        #             to cover both web and mobile? or just app?
        #             what about keeping both?
        #             but allowing to set only one of them at same moment?

        return webdriver.Remote(
            command_executor=(
                config.driver_remote_url
                if config.driver_remote_url
                else 'http://127.0.0.1:4723/wd/hub'
            ),
            options=config.driver_options,
        )

    return {  # type: ignore
        'chrome': install_and_build_chrome,
        'firefox': install_and_build_firefox,
        'edge': install_and_build_edge,
        'remote': build_remote_driver,
        'appium': build_appium_driver,
    }.get(
        'appium'
        if (
            config.driver_name == 'appium'
            or (
                config.driver_options
                and 'platformName' in config.driver_options.capabilities
                and config.driver_options.capabilities['platformName'].lower()
                in ['android', 'ios']
            )
        )
        # TODO: consider automatically detect installed browser if driver_name not set
        else (config.driver_name or 'chrome')
        if not config.driver_remote_url
        else 'remote',
        'chrome',
    )()


def _maybe_reset_driver_then_tune_window_and_get_with_base_url(config: Config):
    def get(url: Optional[str] = None) -> None:
        stored_driver: WebDriver = persistent.Field.value_from(
            config, 'driver'
        )
        if (
            config._reset_not_alive_driver_on_get_url
            and config.is_driver_set_strategy(stored_driver)
            and not callable(stored_driver)
            and not config.is_driver_alive_strategy(stored_driver)
        ):
            # TODO: consider logging this reset
            #       so user will see it and decide to disable it
            config.driver = typing.cast(WebDriver, ...)

        driver = config.driver

        relative_or_absolute_url = url
        if relative_or_absolute_url is None:
            # force to init driver and open browser or app (for mobile)
            # _ = config.driver  # TODO: why not doing this in all cases?
            if not config.base_url:
                # do nothing more
                return
            if not config._get_base_url_on_open_with_no_args:
                # yet do nothing more
                return
            # proceed with adjusted relative url
            # to be concatenated with base url
            relative_or_absolute_url = ''

        # TODO: skip for mobile
        width = config.window_width
        height = config.window_height

        if width or height:
            if not (width and height):
                size = driver.get_window_size()
                width = width or size['width']
                height = height or size['height']

            driver.set_window_size(int(width), int(height))

        is_absolute = helpers.is_absolute_url(relative_or_absolute_url)
        base_url = config.base_url
        url = (
            relative_or_absolute_url
            if is_absolute
            else base_url + relative_or_absolute_url
        )

        # TODO: should we wrap it into wait? at least for logging?
        driver.get(url)

    return get


class ManagedDriverDescriptor:
    def __init__(
        self, *, default: typing.Union[Optional[WebDriver], ...] = ...  # type: ignore
    ):
        self.default = default
        self.name = None

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self

        config = typing.cast(Config, instance)
        # Below...
        # we can't access driver via config.driver explicitly
        # or implicitly by calling other config.* methods,
        # because it will lead to recursion!!!

        driver_box = typing.cast(
            persistent.Box[WebDriver], getattr(config, self.name)
        )
        if driver_box.value is ... or (
            # TODO: think on: if turned on, may slow down tests...
            #       especially when running remote tests...
            config.rebuild_not_alive_driver
            and not callable(driver_box.value)  # TODO: consider deprecating
            and not config.is_driver_alive_strategy(driver_box.value)
        ):
            driver = config.build_driver_strategy(config)
            driver_box.value = driver
            config._schedule_driver_teardown_strategy(config, lambda: driver)

        value = driver_box.value
        if callable(value):
            # warnings.warn(
            #     'Providing driver as callable might be deprecated in future. '
            #     'Consider customizing driver management '
            #     'via other config.* options',
            #     FutureWarning,
            # )
            return value()

        return value

    def __set__(self, instance, value):
        config = typing.cast(Config, instance)

        if not hasattr(instance, self.name):
            # setting this attribute for the first time,
            # probably (TODO: probably or for sure?) in the __init__ method

            if isinstance(value, persistent.Box):
                # it's a boxed value,
                # probably passed implicitly via `persistent.replace`
                driver_box = value
            elif inspect.isdatadescriptor(value):
                # the value happened to be a descriptor
                # it's either object of this descriptor type (`type(self)`)
                # or custom provided descriptor during init new object
                if type(value) is type(self):
                    # we are processing this `self` descriptor as value
                    # so, instead of value, we should store `self.default`
                    driver_box = persistent.Box(self.default)
                else:
                    # somebody decided to provide his own descriptor object
                    # Heh:) It was a good try, but no ;P
                    raise TypeError(
                        'Providing custom descriptor objects on init '
                        'to customize driver management is not supported, '
                        'because it would be too limited... '
                        'You would be able to provide it only on init,'
                        'and use it only via attribute access,'
                        'without possibility to override value with `persistent.replace` '
                        'or `config.with_(**optioins_to_override)`. '
                        'If you want to use custom descriptor, '
                        'you have to subclass Config and provide your descriptor object'
                        'on class attributes definition level.'
                    )  # TODO: cover with tests
            else:
                # setting WebDriver instance directly on init
                driver_box = persistent.Box(value)

                # TODO: here we could remember somehow that driver was set manually
                #       do we need this?

                if not callable(value):
                    config._schedule_driver_teardown_strategy(
                        config, lambda: value
                    )

            setattr(instance, self.name, driver_box)
        else:
            # setting WebDriver instance after init
            driver_box = getattr(instance, self.name)
            driver_box.value = value

            # TODO: should not we check value set above,
            #       wasn't the same as was in driver_box.value before?
            #       if yes, we might not want to add one more atexit handler
            if not callable(value):
                config._schedule_driver_teardown_strategy(
                    config, lambda: value
                )


@persistent.dataclass
class Config:
    """
    A one cross-cutting-concern-like object to group all options
    that might influence Selene behavior depending on context.
    As option the driver instance is also considered.
    More over, this config is not just config,
    but fully manages the driver lifecycle.
    By this we definitely break SRP principle...
    In the name of Good:D. Kind of;).

    All this makes it far from being a simple options data class...
    – yet kept as one «class for everything» to keep things easier to use,
    especially taking into account some historical reasons of Selene's design,
    that was influenced a lot by the Selenide from Java world.
    As a result sometimes options are not consistent with each other,
    when we speak about different contexts of their usage.
    For example, this same config,
    once customized with `config.driver_options = UiAutomator2Options()`,
    will result in mobile driver built, but then all other web-related options,
    for example, a `config.base_url` will be not relevant.
    Some of them will be ignored, while some of them,
    for example js-related, like `config.set_value_by_js`,
    will break the code execution (JavaScript does not work in mobile apps).
    In an ideal world, we would have to split this config into several ones,
    starting BaseConfig and continuing with WebConfig, MobileConfig, etc.
    Yet, we have what we have. This complicates things a bit,
    especially for us, contributors of Selene,
    but makes easier for newbies in a lot of "harder" cases,
    like customizing same shared browser instance for multi-platform test runs,
    when we have one test that works for all platforms.
    Thus, we allow to do "harder" tasks easier for "less experienced" users.
    Again, such "easiness" does not mean "simplicity" for us, contributors,
    and also for advanced Selene users,
    who want to customize things in a lot of ways
    and have them easier to support on a long run.
    But for now, let's keep it as is, considered as a trade-off.
    """

    build_driver_strategy: Callable[
        [Config], WebDriver
    ] = _build_local_driver_by_name_or_remote_by_url_and_options
    """
    A factory to build a driver instance based on this config instance.
    The driver built with this factory will be available via `config.driver`.
    Hence, you can't use `config.driver` directly inside this factory,
    because it may lead to recursion.

    The default factory builds:
    * either a local driver by value specified in `config.name`
    * or remote driver by value specified in `config.driver_remote_url`.
    """

    # TODO: isn't this option too much?
    #       having it, we have to keep driver descriptor definition
    #       after this option definition,
    #       that is pretty tightly coupled...
    #       heh, but maybe we definitely have to keep it defined
    #       after all "strategy" options...
    # Currently we don't use the power of get_driver being callable...
    # It would work even if we pass simply driver instance...
    # Should we simplify things? Or keep it as is with get_driver?
    _schedule_driver_teardown_strategy: Callable[
        [Config, Callable[[], WebDriver]],
        typing.Union[None, typing.Any],
    ] = lambda config, get_driver: atexit.register(
        lambda: config._teardown_driver_strategy(config, get_driver())
    )

    _teardown_driver_strategy: Callable[
        [Config, WebDriver], None
    ] = lambda config, driver: (
        driver.quit()
        if not config.hold_driver_at_exit
        and config.is_driver_set_strategy(driver)
        and config.is_driver_alive_strategy(driver)
        else None
    )

    # TODO: should we make it private so far?
    # TODO: shouldn't it be config-based?
    is_driver_set_strategy: Callable[[WebDriver], bool] = lambda driver: (
        driver is not ... and driver is not None
    )

    # TODO: should we make it private so far?
    is_driver_alive_strategy: Callable[[WebDriver], bool] = lambda driver: (
        # on_error_return_false(lambda: driver.title is not None)
        (
            driver.service.process is not None
            and driver.service.process.poll() is None
        )
        if hasattr(driver, 'service')
        else on_error_return_false(lambda: driver.window_handles is not None)
    )

    driver_options: Optional[BaseOptions] = None

    # Probably, more precise and technically correct name and signature would be:
    #     driver_remote_connection: Optional[Union[str, RemoteConnection]] = None
    # But we decided to keep it more simple and user-friendly
    # in context of the majority of use cases when we just need to pass a URL:
    # for appium and remote cases
    driver_remote_url: Optional[str] = None
    """
    A URL to be used as remote server address to instantiate a RemoteConnection
    to be used by RemoteWebDriver to connect to the remote server.

    Also known as `command_executor`,
    when passing on init: `driver = remote.WebDriver(command_executor=HERE)`.
    Currently we name it and type hint as URL,
    but if you pass a RemoteConnection object,
    it will work same way as in Selenium WebDriver.
    """

    # TODO: consider setting to None or ... by default,
    #       and pick up by factory any installed browser in a system
    driver_name: str = 'chrome'
    """
    A desired name of the driver to build by `config.build_driver_strategy`.
    It is ignored by default `config.build_driver_strategy`
    if `config.driver_remote_url` is set.

    GIVEN set to any of: 'chrome', 'firefox', 'edge',
    AND config.driver is left unset (default value is ...),
    THEN default config.build_driver_strategy will automatically install drivers
    AND build webdriver instance for you
    AND this config will store the instance in config.driver
    """

    # TODO: finalize the name of this option and consider making public
    _override_driver_with_all_driver_like_options: bool = True
    """
    Controls whether driver will be deep copied
    with `config.driver_name`, `config.driver_remote_url`,
    and so for any other `config.*driver*` option.
    when customizing config via `config.with_(**options_to_override)`.

    Examples:
        Building 2 drivers with implicit deep copy of driver storage:

        >>> chrome_config = Config(
        >>>     driver_name='chrome',
        >>>     timeout=10.0,
        >>>     base_url='https://autotest.how',
        >>> )
        >>> chrome = chrome_config.driver
        >>> firefox_config = chrome_config.with_(driver_name='firefox')
        >>> firefox = firefox_config.driver
        >>> assert firefox is not chrome

        Building 2 drivers with explicit deep copy of driver storage [1]:

        >>> chrome_config = Config(
        >>>     driver_name='chrome',
        >>>     timeout=10.0,
        >>>     base_url='https://autotest.how',
        >>>     _override_driver_with_all_driver_like_options=False,
        >>> )
        >>> chrome = chrome_config.driver
        >>> firefox_config = chrome_config.with_(driver_name='firefox', driver=...)
        >>> firefox = firefox_config.driver
        >>> assert firefox is not chrome

        Building 2 drivers with explicit deep copy of driver storage [2]:

        >>> chrome_config = Config(
        >>>     driver_name='chrome',
        >>>     timeout=10.0,
        >>>     base_url='https://autotest.how',
        >>> )
        >>> chrome_config._override_driver_with_all_driver_like_options = False
        >>> chrome = chrome_config.driver
        >>> firefox_config = chrome_config.with_(name='firefox', driver=...)
        >>> firefox = firefox_config.driver
        >>> assert firefox is not chrome

        Building 1 driver because driver storage was not copied:

        >>> chrome_config = Config(
        >>>     driver_name='chrome',
        >>>     timeout=10.0,
        >>>     base_url='https://autotest.how',
        >>> )
        >>> chrome_config._override_driver_with_all_driver_like_options = False
        >>> chrome = chrome_config.driver
        >>> firefox_config = chrome_config.with_(name='firefox')
        >>> firefox = firefox_config.driver
        >>> assert firefox is chrome  # o_O ;)
    """

    # TODO: consider to deprecate because might confuse in case of Appium usage
    @property
    def browser_name(self) -> str:
        return self.driver_name

    # TODO: consider to deprecate because might confuse in case of Appium usage
    @browser_name.setter
    def browser_name(self, value: str):
        self.driver_name = value

    # TODO: do we need it?
    # quit_last_driver_on_reset: bool = False
    # """Controls whether driver will be automatically quit at reset of config.driver"""

    hold_driver_at_exit: bool = False
    """
    Controls whether driver will be automatically quit at process exit or not.

    Will not take much effect for 4.5.0 < selenium versions <= 4.8.3 < ?.?.?,
    Because for some reason, Selenium of such versions kills driver by himself,
    regardless of what Selene thinks about it:D
    """

    @property
    def hold_browser_open(self) -> bool:
        warnings.warn(
            'Was deprecated because "browser" term '
            'is not relevant to mobile context. '
            'Use `config.hold_driver_at_exit` instead',
            DeprecationWarning,
        )
        return self.hold_driver_at_exit

    @hold_browser_open.setter
    def hold_browser_open(self, value: bool):
        warnings.warn(
            'Was deprecated because "browser" term '
            'is not relevant to mobile context. '
            'Use `config.hold_driver_at_exit = ...` instead',
            DeprecationWarning,
        )
        self.hold_driver_at_exit = value

    # TODO: maybe like this:
    #         _driver_get_url_strategy: Callable[[Config, str], None] = get_driver
    #       or should we implement same "decorator-like" style
    #       for other config-based strategies too?
    # TODO: refactor to inline definition with lambda style
    _driver_get_url_strategy: Callable[
        [Config],
        Callable[[Optional[str]], None],
    ] = _maybe_reset_driver_then_tune_window_and_get_with_base_url

    # TODO: consider adding option to reset driver on browser.open if is not alive
    _reset_not_alive_driver_on_get_url: bool = True
    """
    Controls whether driver should be automatically rebuilt
    if it was noticed as not alive (e.g. after quit or crash)
    on next call to `config.driver.get(url)`
    (via `config._driver_get_url_strategy`).

    Does not work if `config.driver` was set manually to `Callable[[], WebDriver]`.

    Is a more "week" option than `config.rebuild_not_alive_driver`,
    that is disabled by default,
    that forces to rebuild driver on any next access.
    """

    rebuild_not_alive_driver: bool = False
    """
    Controls whether driver should be automatically rebuilt
    when on next call to config.driver
    it was noticed as not alive (e.g. after quit or crash).

    May slow down your tests if running against remote Selenium server,
    e.g. Grid or selenoid, because of additional request to check
    if driver is alive per each driver action.

    Does not work if `config.driver` was set manually to `Callable[[], WebDriver]`.

    Is a more "strong" option than `config._reset_not_alive_driver_on_get_url`,
    (enabled by default), that schedules rebuilding driver
    on next access only inside "get url" logic.
    """

    # TODO: consider allowing to provide a Descriptor as a value
    #       by inheritance like:
    #           class MyConfig(Config):
    #              driver: WebDriver = HERE_DriverDescriptor(...)
    #       and then `MyConfig(driver=...)` will work as expected
    # TODO: should we accept a callable here to bypass build_driver_strategy logic?
    #       currently we do... we don't show it explicitly...
    #       but the valid type is Union[WebDriver, Callable[[], WebDriver]]
    #       so... should we do it?
    #       why not just use config.build_driver_strategy for same?
    #       there is the difference though...
    #       the driver factory is only used as a driver builder,
    #       it does not cover other stages of driver lifecycle,
    #       like teardown...
    #       but if we provide a callable instance to driver,
    #       then it will just substitute the whole lifecycle
    driver: WebDriver = ManagedDriverDescriptor(default=...)  # type: ignore
    """
    A driver instance with lifecycle managed by this config special options
    (TODO: specify these options...),
    depending on their values and customization of this attribute.

    GIVEN unset, i.e. equals to default `...`,
    WHEN accessed first time (e.g. via config.driver)
    THEN it will be set to the instance built by `config.build_driver_strategy`.

    GIVEN set manually to an existing driver instance,
          like: `config.driver = Chrome()`
    THEN it will be reused as it is on any next access
    WHEN reset to `...`
    THEN will be rebuilt by `config.build_driver_strategy`

    GIVEN set manually to an existing driver instance (not callable),
          like: `config.driver = Chrome()`
    AND at some point of time the driver is not alive
        like crashed or quit
    AND `config._reset_not_alive_driver_on_get_url` is set to `True`,
        that is default
    WHEN driver.get(url) is requested under the hood
         like at `browser.open(url)`
    THEN config.driver will be reset to `...`
    AND thus will be rebuilt by `config.build_driver_strategy`

    GIVEN set manually to a callable that returns WebDriver instance
          (currently marked with FutureWarning, so might be deprecated)
    WHEN accessed fist time
    AND any next time
    THEN will call the callable and return the result

    GIVEN unset or set manually to not callable
    AND `config.hold_driver_at_exit` is set to `False` (that is default)
    WHEN the process exits
    THEN driver will be quit.
    """

    timeout: float = 4
    poll_during_waits: int = 100
    """
    a fake option, not currently used in Selene waiting:)
    """

    # --- Web-specific options ---
    # TODO: should we pass here None?
    #       and use "not None" as _get_base_url_on_open_with_no_args=True?
    # TODO: should we rename it to app_url? or even just app?
    #       and use it as app capability for mobile?
    #       if not set in driver_options...
    base_url: str = ''
    # TODO: when adding driver_get_url_strategy
    #       should we rename it to get_base_url_when_relative_url_is_missed?
    #       should we use driver term in the name?
    _get_base_url_on_open_with_no_args: bool = False
    window_width: Optional[int] = None
    window_height: Optional[int] = None
    log_outer_html_on_failure: bool = False
    set_value_by_js: bool = False
    type_by_js: bool = False
    click_by_js: bool = False
    wait_for_no_overlap_found_by_js: bool = False

    # TODO: better name? now technically it's not a decorator but decorator_builder...
    # or decorator_factory...
    # yet in python they call it just «decorator with args» or «decorator with params»
    # so technically we are correct naming it simply _wait_decorator
    # by type hint end users yet will see the real signature
    # and hence guess its «builder-like» nature
    # yet... should we for verbosity distinguish options
    # that a decorator factories from options that are simple decorators?
    # maybe better time to decide on this will be once we have more such options :p
    _wait_decorator: Callable[
        [Wait[E]], Callable[[F], F]
    ] = lambda w: lambda f: f

    hook_wait_failure: Optional[Callable[[TimeoutException], Exception]] = None
    '''
    A handler for all exceptions, thrown on failed waiting for timeout.
    Should process the original exception and rethrow it or the modified one.

    TODO: why we name it as hook_* why not handle_* ?
          what would be proper style?
    '''

    reports_folder: str = os.path.join(
        os.path.expanduser('~'),
        '.selene',
        'screenshots',
        str(round(time.time() * 1000)),
    )
    save_screenshot_on_failure: bool = True
    save_page_source_on_failure: bool = True
    # TODO: consider making public
    _counter: itertools.count = itertools.count(
        start=int(round(time.time() * 1000))
    )
    """
    A counter, currently used for incrementing screenshot names
    """
    # TODO: add stubs?
    last_screenshot: Optional[str] = None
    last_page_source: Optional[str] = None
    # TODO: is a _strategy suffix a good naming convention in this context?
    #       maybe yes, because we yet accept config in it...
    #       so we expect it to be a Strategy of some bigger Context
    _save_screenshot_strategy: Callable[
        [Config, Optional[str]], Any
    ] = lambda config, path=None: fp.thread(
        path,
        lambda path: (
            config._generate_filename(suffix='.png') if path is None else path
        ),
        lambda path: (
            os.path.join(path, f'{next(config._counter)}.png')
            if path and not path.lower().endswith('.png')
            else path
        ),
        fp.do(
            fp.pipe(
                os.path.dirname,
                lambda folder: (
                    os.makedirs(folder)
                    if folder and not os.path.exists(folder)
                    else ...
                ),
            )
        ),
        fp.do(
            lambda path: (
                warnings.warn(
                    "name used for saved screenshot does not match file "
                    "type. It should end with an `.png` extension",
                    UserWarning,
                )
                if not path.lower().endswith('.png')
                else ...
            )
        ),
        lambda path: (
            path if config.driver.get_screenshot_as_file(path) else None
        ),
        fp.do(
            lambda path: setattr(config, 'last_screenshot', path)
        ),  # On refactor>rename, we may miss it here :( better would be like:
        #  setattr(config, config.__class__.last_screenshot.name, path)
        #  but currently .name will return '__boxed_last_screenshot' :(
        #  think on how we can resolve this...
    )

    _save_page_source_strategy: Callable[
        [Config, Optional[str]], Any
    ] = lambda config, path=None: fp.thread(
        path,
        lambda path: (
            config._generate_filename(suffix='.html') if path is None else path
        ),
        lambda path: (
            os.path.join(path, f'{next(config._counter)}.html')
            if path and not path.lower().endswith('.html')
            else path
        ),
        fp.do(
            fp.pipe(
                os.path.dirname,
                lambda folder: (
                    os.makedirs(folder)
                    if folder and not os.path.exists(folder)
                    else ...
                ),
            )
        ),
        fp.do(
            lambda path: (
                warnings.warn(
                    "name used for saved page source does not match file "
                    "type. It should end with an `.html` extension",
                    UserWarning,
                )
                if not path.lower().endswith('.html')
                else ...
            )
        ),
        lambda path: (path, config.driver.page_source),
        fp.do(lambda path_and_source: fp.write_silently(*path_and_source)),
        lambda path_and_source: path_and_source[0],
        fp.do(
            lambda path: setattr(config, 'last_page_source', path)
        ),  # On refactor>rename, we may miss it here :( better would be like:
        #  setattr(config, config.__class__.last_screenshot.name, path)
        #  but currently .name will return '__boxed_last_screenshot' :(
        #  think on how we can resolve this...
    )

    # TODO: consider adding option to disable persistence of all not-overridden options
    #       or marking some of them as not persistent
    #       (i.e. unbind some of them keeping the previous value set)
    def with_(self, **options_to_override) -> Config:
        """

        Parameters:
            **options_to_override:
                options to override in the new config.

                Technically "override" here means:
                "deep copy option storage and update its value to the specified one".
                All other option storages will be:
                "shallow copied from the current config".

                If `driver_name` is among `options_to_override`,
                and `driver` is not among them,
                and `self._override_driver_with_all_driver_like_options` is True,
                then `driver` will be implicitly added to the options to override,
                i.e. `with_(driver_name='firefox')` will be equivalent
                to `with_(driver_name='firefox', driver=...)`.
                The latter gives a readable and concise shortcut
                to spawn more than one browser:

                >>> config = Config(timeout=10.0, base_url='https://autotest.how')
                >>> chrome = config.driver  # chrome is default browser
                >>> firefox_config = config.with_(driver_name='firefox')
                >>> firefox = firefox_config.driver
                >>> edge_config = config.with_(driver_name='edge')
                >>> edge = edge_config.driver

                Same logic applies to `remote_url`,
                and all other config.*driver* options.

        Returns:
            a new config with overridden options that were specified as arguments.

            All other config options will be shallow-copied
            from the current config.
            Those other options that are of immutable types,
            like `int` – will be also copied by reference,
            i.e. in a truly shallow way.
        """
        options = (
            {'driver': ..., **options_to_override}
            if (
                self._override_driver_with_all_driver_like_options
                and 'driver' not in options_to_override
                and any('driver' in key for key in options_to_override)
            )
            else options_to_override
        )
        return persistent.replace(self, **options)

    def _generate_filename(self, prefix='', suffix=''):
        path = self.reports_folder
        next_id = next(self._counter)
        filename = f'{prefix}{next_id}{suffix}'
        file = os.path.join(path, f'{filename}')

        folder = os.path.dirname(file)
        if not os.path.exists(folder) and folder:
            os.makedirs(folder)

        return file

    # TODO: consider moving this injection to the WaitingEntity.wait method
    #       to build Wait object instead of config.wait
    def _inject_screenshot_and_page_source_pre_hooks(self, hook):
        # TODO: consider moving hooks to class methods accepting config as argument
        #       or refactor somehow to eliminate all times defining hook fns
        def save_and_log_screenshot(error: TimeoutException) -> Exception:
            path = self._save_screenshot_strategy(self)
            return TimeoutException(
                error.msg
                + f'''
Screenshot: file://{path}'''
            )

        def save_and_log_page_source(error: TimeoutException) -> Exception:
            filename = (
                # TODO: this dependency to last_page_source might lead to code,
                #       when wrong last_page_source name is taken
                self.last_screenshot.replace('.png', '.html')
                if self.last_screenshot
                else self._generate_filename(suffix='.html')
            )

            path = self._save_page_source_strategy(self, filename)
            return TimeoutException(error.msg + f'\nPageSource: file://{path}')

        return fp.pipe(
            save_and_log_screenshot
            if self.save_screenshot_on_failure
            else None,
            save_and_log_page_source
            if self.save_page_source_on_failure
            else None,
            hook,
        )

    # TODO: we definitely not need it inside something called Config,
    #       especially "base interface like config
    #       consider refactor to wait_factory as configurable config property
    def wait(self, entity):
        hook = self._inject_screenshot_and_page_source_pre_hooks(
            self.hook_wait_failure
        )
        return Wait(
            entity,
            at_most=self.timeout,
            or_fail_with=hook,
            _decorator=self._wait_decorator,
        )
