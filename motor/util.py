# Copyright 2013 10gen, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""A version of PyMongo's thread_util for Motor."""


import weakref
import datetime

try:
    from time import monotonic as _time
except ImportError:
    from time import time as _time

import greenlet


# TODO: test.
class MotorGreenletEvent(object):
    """An Event-like class for greenlets."""
    def __init__(self, io_loop):
        self.io_loop = io_loop
        self._flag = False
        self._waiters = set()  # TODO: a list instead?
        self._timeouts = set()

    def is_set(self):
        return self._flag

    isSet = is_set

    def set(self):
        self._flag = True
        timeouts, self._timeouts = self._timeouts, set()
        for timeout in timeouts:
            self.io_loop.remove_timeout(timeout)

        waiters, self._waiters = self._waiters, set()
        for waiter in waiters:
            # Defer execution.
            self.io_loop.add_callback(waiter.switch)

    def clear(self):
        self._flag = False

    def wait(self, timeout_seconds=None):
        current = greenlet.getcurrent()
        parent = current.parent
        assert parent, "Should be on child greenlet"
        if not self._flag:
            self._waiters.add(current)

            def on_timeout():
                # Called from IOLoop on main greenlet.
                self._waiters.remove(current)
                self._timeouts.remove(timeout)
                current.switch()

            if timeout_seconds is not None:
                timeout = self.io_loop.add_timeout(
                    datetime.timedelta(seconds=timeout_seconds), on_timeout)

                self._timeouts.add(timeout)
            parent.switch()
