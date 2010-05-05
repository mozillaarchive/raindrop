#!/usr/bin/env python
# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is Raindrop.
#
# The Initial Developer of the Original Code is
# Mozilla Messaging, Inc..
# Portions created by the Initial Developer are Copyright (C) 2009
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#

import sys
import os
import tempfile
import raindrop.tests

# explicit python version check here incase they haven't installed
# unittest2 - we don't want auto fallback to the old one.
if sys.hexversion > (2,7):
    import unittest
else:
    try:
        import unittest2 as unittest
    except ImportError:
        print >> sys.stderr, "The raindrop tests require the 'unittest2' package."
        print >> sys.stderr, "Please 'easy_install unittest2' and try again."
        sys.exit(1)

# All we are doing here is (a) auto-discovery of tests and (b) supporting
# an optional list of matching test names to run on the cmd-line.
class TestProgram(unittest.TestProgram):
    def parseArgs(self, argv):
        import optparse
        parser = optparse.OptionParser()
        parser.add_option('-v', '--verbose', dest='verbose', default=False,
                          help='Verbose output', action='store_true')

        options, args = parser.parse_args(argv[1:])
        if options.verbose:
            self.verbosity = 2

        start_dir = raindrop.tests.__path__[0]
        pattern = "test*.py"
        top_level_dir = None

        loader = unittest.loader.TestLoader()
        test = loader.discover(start_dir, pattern, top_level_dir)
        if args:
            # saly we get back a test suite, so dig inside.
            self.test = loader.suiteClass()
            self._find_matching(test, args)
            if not self.test._tests:
                parser.error("No tests match %s" % (args,))
        else:
            self.test = test

    def _find_matching(self, tests, patterns):
        # recursively walks down test suite objects and adds matching tests
        # to *our* test suite object...
        for t in tests:
            if isinstance(t, self.test.__class__):
                # a test suite - walk its tests...
                self._find_matching(t, patterns)
            else:
                for p in patterns:
                    if t.id().startswith(p):
                        self.test.addTest(t)

# now run it...
if __name__=='__main__':
    TestProgram()
