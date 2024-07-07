# MIT License
#
# Copyright (c) 2015-2022 Iakiv Kramarenko
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
import pytest

from selene import have, be
from selene.core import match
from tests.integration.helpers.givenpage import GivenPage
from tests import const


# todo: consider breaking it down into separate tests


def test_should_match_different_things(session_browser):
    s = lambda selector: session_browser.with_(timeout=0.1).element(selector)
    ss = lambda selector: session_browser.with_(timeout=0.1).all(selector)
    GivenPage(session_browser.driver).opened_with_body(
        '''
        <ul>
        <!--<li id="absent"></li>-->
        <li id="hidden-empty" style="display: none"></li>
        <li id="hidden" style="display: none"> One  !!!
        </li>
        <li id="visible-empty" style="display: block"></li>
        <li id="visible" style="display: block"> One  !!!
        </li>
        </ul>
        <!--<input id="absent"></li>-->
        <input id="hidden-empty" style="display: none">
        <input id="hidden" style="display: none" value=" One  !!!">
        <input id="visible-empty" style="display: block" value="">
        <input id="visible" style="display: block" value=" One  !!!">
        <!--etc...-->
        <ul>Hey:
           <li><label>First Name:</label> <input type="text" class="name" id="firstname" value="John 20th"></li>
           <li><label>Last Name:</label> <input type="text" class="name" id="lastname" value="Doe 2nd"></li>
        </ul>
        <ul>Your training today:
           <li><label>Pull up:</label><input type="text" class='exercise' id="pullup" value="20"></li>
           <li><label>Push up:</label><input type="text" class='exercise' id="pushup" value="30"></li>
        </ul>
        '''
    )

    # THEN

    # have tag?
    # - visible passes
    s('li#visible').should(match.tag('li'))
    s('li#visible').should(have.tag('li'))
    s('input#visible').should(have.no.tag('input').not_)
    s('input#visible').should(have.tag('input').not_.not_)
    # - hidden passes
    s('li#hidden').should(match.tag('li'))
    s('li#hidden').should(have.tag('li'))
    s('input#hidden').should(have.no.tag('input').not_)
    s('input#hidden').should(have.tag('input').not_.not_)
    # have tag containing?
    # - visible passes
    s('li#visible').should(match.tag_containing('l'))
    s('li#visible').should(have.tag_containing('l'))
    s('input#visible').should(have.no.tag_containing('in').not_)
    s('input#visible').should(have.tag_containing('in').not_.not_)
    # - hidden passes
    s('li#hidden').should(match.tag_containing('l'))
    s('li#hidden').should(have.tag_containing('l'))
    s('input#hidden').should(have.no.tag_containing('in').not_)
    s('input#hidden').should(have.tag_containing('in').not_.not_)
    # absent fails with failure
    try:
        s('li#absent').should(have.tag('li'))
        pytest.fail('expect FAILURE')
    except AssertionError as error:
        assert (
            "browser.element(('css selector', 'li#absent')).has tag li\n"
            '\n'
            'Reason: NoSuchElementException: no such element: Unable to locate element: '
            '{"method":"css selector","selector":"li#absent"}\n'
        ) in str(error)
    # have no tag?
    s('li#visible').should(have.no.tag('input'))
    s('input#visible').should(have.no.tag('li'))
    # have no tag containing?
    s('li#visible').should(have.no.tag_containing('in'))
    s('input#visible').should(have.no.tag_containing('l'))


def test_should_be_emtpy__applied_to_non_form__passed_and_failed__compared(
    session_browser,
):
    s = lambda selector: session_browser.with_(timeout=0.1).element(selector)
    ss = lambda selector: session_browser.with_(timeout=0.1).all(selector)
    GivenPage(session_browser.driver).opened_with_body(
        '''
        <ul>
        <!--<li id="absent"></li>-->
        <li id="hidden-empty" style="display: none"></li>
        <li id="hidden" style="display: none"> One  !!!
        </li>
        <li id="visible-empty" style="display: block"></li>
        <li id="visible" style="display: block"> One  !!!
        </li>
        </ul>
        <!--<input id="absent"></li>-->
        <form id="form-no-text-with-values">
            <div id="empty-inputs">
                <input id="hidden-empty" style="display: none">
                <input id="visible-empty" style="display: block" value="">
            </div>
            <div id="non-empty-inputs">
                <input id="hidden" style="display: none" value=" One  !!!">
                <input id="visible" style="display: block" value=" One  !!!">
            </div>
        </form>
        <form id="form-with-text-with-values">
            <div id="empty-inputs">
                <input id="hidden-empty-2" style="display: none">
                <label>Visible empty:</label>
                <input id="visible-empty-2" style="display: block" value="">
            </div>
            <div id="non-empty-inputs">
                <input id="hidden-2" style="display: none" value=" One  !!!">
                <label>Visible:</label>
                <input id="visible-2" style="display: block" value=" One  !!!">
            </div>
        </form>
        <!--etc...-->
        <ul>Hey:
           <li><label>First Name:</label> <input type="text" class="name" id="firstname" value="John 20th"></li>
           <li><label>Last Name:</label> <input type="text" class="name" id="lastname" value="Doe 2nd"></li>
        </ul>
        <ul>Your training today:
           <li><label>Pull up:</label><input type="text" class='exercise' id="pullup" value="20"></li>
           <li><label>Push up:</label><input type="text" class='exercise' id="pushup" value="30"></li>
        </ul>
        '''
    )

    # be empty vs have size vs be blank + inverted?
    ss('.exercise').should(have.size(2))
    ss('.exercise').should(have.no.size(0))
    ss('.exercise').should(be.not_._empty)
    ss('#visible').should(have.size(2))
    ss('#visible').should(have.no.size(0))
    ss('#visible').should(be.not_._empty)
    ss('#hidden').should(have.size(2))
    try:
        ss('#hidden').should(have.size(0))
        pytest.fail('expect mismatch')
    except AssertionError as error:
        assert (
            "browser.all(('css selector', '#hidden')).has size 0\n"
            '\n'
            'Reason: ConditionMismatch: actual size: 2\n'
        ) in str(error)
    try:
        ss('#hidden').should(be._empty)
        pytest.fail('expect mismatch')
    except AssertionError as error:
        assert (
            "browser.all(('css selector', '#hidden')).is empty\n"
            '\n'
            'Reason: ConditionMismatch: actual size: 2\n'
        ) in str(error)
    try:
        s('input#visible').should(be.blank)
        pytest.fail('expect mismatch')
    except AssertionError as error:
        assert (
            "browser.element(('css selector', 'input#visible')).is blank\n"
            '\n'
            'Reason: ConditionMismatch: actual value:  One  !!!\n'
        ) in str(error)
    try:
        s('input#visible').should(be._empty)
        pytest.fail('expect mismatch')
    except AssertionError as error:
        assert (
            "browser.element(('css selector', 'input#visible')).is empty\n"
            '\n'
            'Reason: ConditionMismatch: actual value:  One  !!!\n'
        ) in str(error)
    try:
        s('li#visible').should(be.blank)
        pytest.fail('expect mismatch')
    except AssertionError as error:
        assert (
            "browser.element(('css selector', 'li#visible')).is blank\n"
            '\n'
            'Reason: ConditionMismatch: actual text: One !!!\n'
        ) in str(error)
    try:
        s('li#visible').should(be._empty)
        pytest.fail('expect mismatch')
    except AssertionError as error:
        assert (
            "browser.element(('css selector', 'li#visible')).is empty\n"
            '\n'
            'Reason: ConditionMismatch: actual text: One !!!\n'
        ) in str(error)
    ss('#hidden').should(have.no.size(0))
    ss('#hidden').should(be.not_._empty)
    ss('.absent').should(have.size(0))
    try:
        ss('.absent').should(have.no.size(0))
        pytest.fail('expect mismatch')
    except AssertionError as error:
        assert (
            "browser.all(('css selector', '.absent')).has no (size 0)\n"
            '\n'
            'Reason: ConditionMismatch: actual size: 0\n'
        ) in str(error)
    ss('.absent').should(be._empty)
    try:
        ss('.absent').should(be.not_._empty)
        pytest.fail('expect mismatch')
    except AssertionError as error:
        assert (
            "browser.all(('css selector', '.absent')).is not (empty)\n"
            '\n'
            'Reason: ConditionMismatch: actual size: 0\n'
        ) in str(error)
    s('li#visible-empty').should(be.blank)
    s('input#visible-empty').should(be.blank)
    s('li#visible').should(be.not_.blank)
    s('input#visible').should(be.not_.blank)
    s('li#visible-empty').should(be._empty)
    s('input#visible-empty').should(be._empty)
    s('li#visible').should(be.not_._empty)
    s('input#visible').should(be.not_._empty)

    # non-form container elements are considered empty if there is no text inside
    s('#form-no-text-with-values div#empty-inputs').should(be._empty)
    s('#form-no-text-with-values div#non-empty-inputs').should(be._empty)
    s('#form-with-text-with-values div#empty-inputs').should(be.not_._empty)
    s('#form-with-text-with-values div#non-empty-inputs').should(be.not_._empty)


def test_should_be_emtpy__applied_to_form__passed_and_failed(
    session_browser,
):
    s = lambda selector: session_browser.with_(timeout=0.1).element(selector)
    ss = lambda selector: session_browser.with_(timeout=0.1).all(selector)
    GivenPage(session_browser.driver).opened_with_body(
        f'''
        <form id="form-with-text-no-values">
            <textarea id="textarea-no-value-no-text"></textarea>
            <input id="no-type-no-value">
            <input id="no-type-explicit-empty-value" value="">

            <input type="text" id="type-text-no-value">
            <input type="text" id="type-text-explicit-empty-value" value="">

            <input type="checkbox" id="type-checkbox-not-checked" name="vehicle1" value="Bike">
            <label for="vehicle1"> I have a bike</label><br>

            <input type="radio" id="type-radio-not-checked" name="fav_language" value="HTML">
            <label for="html">HTML</label><br>

            <select id="select-empty-value">
                <option value=""></option>
                <option value="volvo">Volvo</option>
                <option value="saab">Saab</option>
                <option value="mercedes">Mercedes</option>
                <option value="audi">Audi</option>
            </select>

            <!--button, submit, reset should be not counted:-->
            <button id="button-no-value-with-text">Click me</button>
            <input type="submit" id="type-submit-with-value" value="Submit">
            <input type="reset" id="type-reset-with-value" value="Reset">

            <!--image and hidden should be not counted:-->
            <input type="image" id="type-image-with-src-no-value" src="{const.LOGO_PATH}">
            <input type="hidden" id="type-hidden-some-value" value="some">

            <!--range and color should be not counted
                because they always have at least 0 and #000000
                that can hardly be counted as "empty"-->
            <input type="range" id="type-range-0-value">
            <input type="color" id="type-color-000000-value">
        </form>

        <form id="form-no-text-no-values">
            <textarea id="textarea-no-value-no-text"></textarea>
            <input id="no-type-no-value">
            <input id="no-type-explicit-empty-value" value="">

            <input type="text" id="type-text-no-value">
            <input type="text" id="type-text-explicit-empty-value" value="">

            <input type="checkbox" id="type-checkbox-not-checked" name="vehicle1" value="Bike">

            <input type="radio" id="type-radio-not-checked" name="fav_language" value="HTML">

            <select id="select-empty-value">
                <option value=""></option>
                <option value="volvo">Volvo</option>
                <option value="saab">Saab</option>
                <option value="mercedes">Mercedes</option>
                <option value="audi">Audi</option>
            </select>

            <!--button, submit, reset should be not counted:-->
            <!--<button id="button-no-value-with-text">Click me</button>-->
            <input type="submit" id="type-submit-with-value" value="Submit">
            <input type="reset" id="type-reset-with-value" value="Reset">

            <!--image and hidden should be not counted:-->
            <input type="image" id="type-image-with-src-no-value" src="{const.LOGO_PATH}">
            <input type="hidden" id="type-hidden-some-value" value="some">

            <!--range and color should be not counted
                because they always have at least 0 and #000000
                that can hardly be counted as "empty"-->
            <input type="range" id="type-range-0-value">
            <input type="color" id="type-color-000000-value">
        </form>

        <form id="form-no-text-with-values">
            <textarea id="textarea-with-value-no-text"></textarea> <!-- value will be set via UI -->
            <input id="no-type-with-value" value="no-type-with-value;">
            <input id="no-type-explicit-empty-value" value="">

            <input type="text" id="type-text-with-value" value="type-text-with-value;">
            <input type="text" id="type-text-explicit-empty-value" value="">

            <input type="checkbox" id="type-checkbox-checked" name="vehicle1" value="Bike" checked>

            <input type="radio" id="type-radio-checked" name="fav_language" value="HTML" checked>

            <select id="select-empty-value">
                <!--<option value=""></option>-->
                <option value="volvo">Volvo</option>
                <option value="saab">Saab</option>
                <option value="mercedes">Mercedes</option>
                <option value="audi">Audi</option>
            </select>

            <!--button, submit, reset should be not counted:-->
            <button id="button-no-value-with-text">Click me</button>
            <input type="submit" id="type-submit-with-value" value="Submit">
            <input type="reset" id="type-reset-with-value" value="Reset">

            <!--image and hidden should be not counted:-->
            <input type="image" id="type-image-with-src-no-value" src="{const.LOGO_PATH}">
            <input type="hidden" id="type-hidden-some-value" value="some">

            <!--range and color should be not counted
                because they always have at least 0 and #000000
                that can hardly be counted as "empty"-->
            <input type="range" id="type-range-0-value">
            <input type="color" id="type-color-000000-value">
        </form>

        <form id="form-with-text-with-values">
            <textarea id="textarea-with-value-with-text">textarea-with-value-with-text;</textarea>
            <input id="no-type-with-value" value="no-type-with-value;">
            <input id="no-type-explicit-empty-value" value="">

            <input type="text" id="type-text-with-value" value="type-text-with-value;">
            <input type="text" id="type-text-explicit-empty-value" value="">

            <input type="checkbox" id="type-checkbox-checked" name="vehicle1" value="Bike" checked>
            <label for="vehicle1"> I have a bike</label><br>

            <input type="radio" id="type-radio-checked" name="fav_language" value="HTML" checked>
            <label for="html">HTML</label><br>

            <select id="select-empty-value">
                <!--<option value=""></option>-->
                <option value="volvo">Volvo</option>
                <option value="saab">Saab</option>
                <option value="mercedes">Mercedes</option>
                <option value="audi">Audi</option>
            </select>

            <!--button, submit, reset should be not counted:-->
            <button id="button-no-value-with-text">Click me</button>
            <input type="submit" id="type-submit-with-value" value="Submit">
            <input type="reset" id="type-reset-with-value" value="Reset">

            <!--image and hidden should be not counted:-->
            <input type="image" id="type-image-with-src-no-value" src="{const.LOGO_PATH}">
            <input type="hidden" id="type-hidden-some-value" value="some">

            <!--range and color should be not counted
                because they always have at least 0 and #000000
                that can hardly be counted as "empty"-->
            <input type="range" id="type-range-0-value">
            <input type="color" id="type-color-000000-value">
        </form>
        '''
    )
    s('#form-no-text-with-values textarea').type('textarea-with-value-no-text;')

    # form element is considered empty if all "text-value" fields are empty
    s('#form-no-text-with-values').should(be.not_._empty)
    try:
        s('#form-no-text-with-values').should(be._empty)
        pytest.fail('expect mismatch')
    except AssertionError as error:
        assert (
            "browser.element(('css selector', '#form-no-text-with-values')).is empty\n"
            '\n'
            'Reason: ConditionMismatch: actual values of all form inputs, textareas and '
            'selects: '
            'textarea-with-value-no-text;no-type-with-value;type-text-with-value;BikeHTMLvolvo\n'
            'Screenshot: '
        ) in str(error)
    s('#form-with-text-with-values').should(be.not_._empty)
    try:
        s('#form-with-text-with-values').should(be._empty)
        pytest.fail('expect mismatch')
    except AssertionError as error:
        assert (
            "browser.element(('css selector', '#form-with-text-with-values')).is empty\n"
            '\n'
            'Reason: ConditionMismatch: actual values of all form inputs, textareas and selects: '
            'textarea-with-value-with-text;no-type-with-value;type-text-with-value;BikeHTMLvolvo\n'
        ) in str(error)
    s('#form-no-text-no-values').should(be._empty)
    try:
        s('#form-no-text-no-values').should(be.not_._empty)
        pytest.fail('expect mismatch')
    except AssertionError as error:
        assert (
            "browser.element(('css selector', '#form-no-text-no-values')).is not (empty)\n"
            '\n'
            'Reason: ConditionMismatch: actual values of all form inputs, textareas and '
            'selects: \n'  # todo: make empty string explicit via quotes (here and everywhere)
            'Screenshot: '
        ) in str(error)
    s('#form-with-text-no-values').should(be._empty)
    try:
        s('#form-with-text-no-values').should(be.not_._empty)
        pytest.fail('expect mismatch')
    except AssertionError as error:
        assert (
            "browser.element(('css selector', '#form-with-text-no-values')).is not "
            '(empty)\n'
            '\n'
            'Reason: ConditionMismatch: actual values of all form inputs, textareas and '
            'selects: \n'
            'Screenshot: '
        ) in str(error)
