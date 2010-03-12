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

from __future__ import with_statement

import ConfigParser, logging, os, os.path

__all__ = ['get_config']

class Config(object):
  COUCH_DEFAULTS = {'host': '127.0.0.1', 'port': 5984, 'name': 'raindrop'}
  COUCH_PREFIX = 'couch-'
  ACCOUNT_PREFIX = 'account-'
  
  def __init__(self, filename=None):
    if not filename:
      filename = "~/.raindrop"
    self.filename = os.path.expanduser(filename)
    self.parser = ConfigParser.SafeConfigParser()

    self.couches = {'local': self.COUCH_DEFAULTS.copy()}
    # the default name of the DB if derived from the filename being used.
    # This is so our API process, which works with many databases at once,
    # can handle all these different DBs in a sane way.
    base = os.path.split(filename)[-1]
    dbname = base.strip(".")
    self.couches['local']['name'] = dbname

    self.accounts = {}

    self.load()

  def dictifySection(self, section_name, defaults=None, name=None):
    '''
    Given a config section name, suck up its contents into a dictionary.  Poor
    man's type detection turns lowercase true/false into the boolean of that
    type, things that can be int()ed into ints, and otherwise things get to
    stay strings.  Defaults are applied before dictification, and the name is
    an optional default for 'name' if specified (which overrides the defaults
    dict.)
    '''
    results = {}
    if defaults:
      results.update(defaults)
    if name:
      results['name'] = name
    for name, value in self.parser.items(section_name):
      if value.lower() in ('true', 'false'):
        value = (value.lower() == 'true')
      else:
        try:
          value = int(value)
        except:
          pass

      results[name] = value
    return results

  def load(self):
    filenames = [self.filename]
    self.parser.read(filenames)

    for section_name in self.parser.sections():
      if section_name.startswith(self.COUCH_PREFIX):
        couch_name = section_name[len(self.COUCH_PREFIX):]
        self.couches[couch_name] = self.dictifySection(section_name,
                                                       self.COUCH_DEFAULTS)

      if section_name.startswith(self.ACCOUNT_PREFIX):
        account_name = section_name[len(self.ACCOUNT_PREFIX):]
        acct = self.accounts[account_name] = \
                    self.dictifySection(section_name, None, account_name)
        acct['id'] = account_name

    self.local_couch = self.couches['local']
    self.remote_couch = self.couches.get('remote') # may be None

  def save_account(self, acct_name, acct_fields):
    assert acct_name.startswith(self.ACCOUNT_PREFIX) # else it will not load!
    if self.parser.has_section(acct_name):
      self.parser.remove_section(acct_name)
    self.parser.add_section(acct_name)
    for name, val in acct_fields.iteritems():
      self.parser.set(acct_name, name, str(val))

    # first save to a temp filename
    temp_name = self.filename + ".temp"
    with open(temp_name, "w") as fp:
      self.parser.write(fp)
    try:
      os.unlink(self.filename)
    except os.error:
      pass
    os.rename(temp_name, self.filename)


# Ack - this is hard - on one hand we want "global" as passing this as a param
# everywhere is hard - on the other hand, the test suite etc makes this is a
# PITA.
CONFIG = None
def get_config():
  assert CONFIG is not None, "init_config not called!"
  return CONFIG

def init_config(config_file=None):
  global CONFIG
  assert CONFIG is None, "already initialized"
  CONFIG = Config(config_file)
  return CONFIG
