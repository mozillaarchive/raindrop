import logging

__all__ = ['Rat', 'AccountBase']

logger = logging.getLogger("accounts")

class Rat(object):
  '''
  Account reasons rationale... this is here to make typing easier...
  '''
  #: all whats for this account
  EVERYTHING = 'everything'
  #: the problem is with the server (or the network)
  SERVER = 'server'
  #: the problem is with the account
  ACCOUNT = 'account'

  UNREACHABLE = 'unreachable'
  PASSWORD = 'password'
  MAINTENANCE = 'maintenance'
  BUSY = 'busy'
  #: something is up with the crypto; this needs to be exploded
  CRYPTO = 'crypto'

  #: good indicates that all-is-well
  GOOD = 'good'
  '''
  Neutral indicates an expected transient lack of success (maintenance,
   overloaded servers, etc.)  It is tracked (rather than silently not updating
   good) because it potentially allows for higher-level logic to escalate
   continued inability to connect to something user-visible.

  For example, twitter being down for short periods of time (at least in the
   past) was business as usual; there would be no reason to notify the user.
   Howerver, if twitter is down for an extended period of time, we want to let
   the user know (in an ambient sort of way) that there's a problem with
   twitter, and that's why they're not getting any messages.

  The primary difference between a TEMPORARY BAD thing and a TEMPORARY NEUTRAL
   thing is that we will let the user know about a TEMPORARY BAD thing
   when it happens.
  '''
  NEUTRAL = 'neutral'
  '''
  Bad indicates an unexpected problem which may be TEMPORARY or PERMANENT.
   Temporary problems are expressed to the user in an ambient fashion when
   they happen, but may not require any action.  If a temporary problem stays
   a problem for an extended period of time, it will be escalated to a
   more explicit notification.  A permanent problem requires user action and
   the user will be immediately notified.

  For example, bad passwords and suspended accounts are permanent problems.  The
   former is actionable within the UI, whereas the latter is not.  However, it
   is important that the user be notified at the earliest opportunity so they
   can take real-world action promptly.  A server being inaccessible is a
   TEMPORARY BAD problem rather than a TEMPORARY NEUTRAL thing because a user
   may benefit from knowing their connection or server is flakey.  (Note:
   temporarily lacking an internet connection is different from a flakey one;
   we don't want to bother the user if we know they don't have a connection.)
  '''
  BAD = 'bad'

  #: temporary implies it may fix itself without user intervention
  TEMPORARY = 'temporary'
  #: permanent implies the user must take some action to correct the problem
  PERMANENT = 'permanent'
  #: unknown means it either doesn't matter or it could be temporary but the
  #:  user should potentially still be informed
  UNKNOWN = 'unknown'


class AccountBase(Rat):
  def __init__(self, doc_model, details):
    self.doc_model = doc_model
    self.details = details

  def reportStatus(self, what, state, why=Rat.UNKNOWN,
                   expectedDuration=Rat.UNKNOWN):
    '''
    Report status relating to this account.

    Everything is peachy: EVERYTHING GOOD
    Wrong password: ACCOUNT BAD PASSWORD PERMANENT
    (may be temporary if a bad password can mean many things)
    Can't contact server: SERVER BAD UNREACHABLE TEMPORARY
    Server maintenance: SERVER NEUTRAL MAINTENANCE TEMPORARY
    (indicates a temporary lapse in service but there's not much we can do)
    Server busy: SERVER NEUTRAL BUSY TEMPORARY
    (for example, last.fm will sometimes refuse submission requests)
    '''
    logger.debug("ReportStatus: %s %s (why=%s, duration=%s)",
                 what, state, why, expectedDuration)

  def sync(self):
    pass

  def verify(self):
    '''
    '''
    pass

# A couple of decorators for use by extensions
def raindrop_extension(src_schema):
    def decorate(f):
        ext_name = f.func_globals['__name__'] + '.' + f.__name__
        f.extension_id = ext_name
        f.source_schema = src_schema
        return f
    return decorate

def raindrop_identity_extension(src_schema):
    def decorate(f):
        ext_name = f.func_globals['__name__'] + '.' + f.__name__
        f.identity_extension_id = ext_name
        f.source_schema = src_schema
        return f
    return decorate


class SpawnerBase(object):
    """A generic spawner with optionally a dependent input document type.

    A spawner makes new 'types' of documents spring into life.  They may
    have no input dependency (in which case documents are created out of
    'thin air' - eg, mapi/skype/twitter messages.)  They may list a doc type
    as a dependency, in which case the spawner looks at documents of its
    source type and uses that to have new docs spring into life.  For example,
    a Spawner may look at a raw skype user and create identity records for
    the user's phone-numbers, etc.

    The spawner is responsible for managing all conflicts etc from records
    it created in the past.
  
    XXX - the above is 'tdb' - in practice we are now specialized into an 'identity
    spawner' - but the intent is that we redefine the 'generic' spawner, and
    the thing which does the identity specific thing is a subclass and
    provides its own 'extension point'. IOW, the pipeline should not be aware
    anything is 'identity' specific - but for now it is... """
    # Attributes we expect our sub-classes to override.
    source_type = None
    # See above - this is really just a 'placeholder' for an interface we
    # are yet to define, and which will provide its own extension points.


class IdentitySpawnerBase(SpawnerBase):
    def __init__(self, doc_model):
        self.doc_model = doc_model
  
    def get_identity_rels(self, source_doc):
        """Returns a sequence of (identity_id, rel_name) tuples.

        For example, something which can detect phone numbers may emit
        [(('phone', '+1234566098'), 'home)]
        """
        raise NotImplementedError(self)

    def get_default_contact_props(self, source_doc):
        """Returns a dictionary with suitable default properties for a new
        contact should we need to create one.  A 'name' field must be
        supplied.
        """
        raise NotImplementedError(self)


class ConverterBase(object):
    """A generic converter with possibly multiple dependencies.
    
    A converter always returns a single new document, which can be considered
    a 'transformation' of the input messages.  The output document is always
    directly related to the input documents, so as a result, the Converter
    doesn't specify the document IDs, deal with conflicts, etc.
    """
    # Attributes we expect our sub-classes to override.
    sources = None # a sequence of source types.
    target_type = None # the target type.
    def __init__(self, doc_model):
      self.doc_model = doc_model
  
    def convert(self, docs):
      raise NotImplementedError(self)


class SimpleConverterBase(ConverterBase):
  """A converter with exactly 1 source dependency"""
  def convert(self, docs):
    assert len(self.sources)==1, "not a simple coonverter!"
    if not docs:
      # source doc doesn't exist.
      return None
    doc = docs[0]
    my_type = self.sources[0][1]
    if doc['type'] != my_type:
      logger.debug('simple converter skipping doc_type of %r (expected %r)',
                   doc['type'], my_type)
      return None
    return self.simple_convert(doc)

  def simple_convert(self, doc):
    raise NotImplementedError(self)
