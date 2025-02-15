from selene import web
from selene.core.condition import Condition, Match
from selene.core.conditions import ElementCondition
from selene.support.conditions.be import *  # noqa
from selene.support.conditions.be import not_ as _original_not_  # noqa

not_ = _original_not_

visible_in_viewport: Condition[web.Element] = Match(
    'is visible in view port',
    by=lambda element: element.execute_script(
        '''
        var rect = element.getBoundingClientRect();

        return (
            rect.top >= 0 &&
            rect.left >= 0 &&
            rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
            rect.right <= (window.innerWidth || document.documentElement.clientWidth)
        );
        '''
    ),
)

not_visible_in_viewport: Condition[web.Element] = visible_in_viewport.not_
