# This is an implementation of a 'test' protocol.
import logging
from twisted.internet import defer, error

logger = logging.getLogger(__name__)

from ...proc import base

class TestMessageProvider(object):
    def __init__(self, account, conductor):
        self.account = account
        self.doc_model = account.doc_model # this is a little confused...
        self.conductor = conductor

    def sync_generator(self):
        num_docs = int(self.account.details.get('num_test_docs', 5))
        logger.info("Creating %d test documents", num_docs)
        for i in xrange(num_docs):
            yield self.check_test_message(i)
        if self.bulk_docs:
            yield self.doc_model.create_raw_documents(self.account,
                                                      self.bulk_docs
                    ).addCallback(self.saved_bulk_messages, len(self.bulk_docs),
                    )

    def attach(self):
        logger.info("preparing to synch test messages...")
        self.bulk_docs = [] # anything added here will be done in bulk
        # use the cooperator for testing purposes.
        return self.conductor.coop.coiterate(self.sync_generator())

    def check_test_message(self, i):
        logger.debug("seeing if message with ID %d exists", i)
        return self.doc_model.open_document("msg", str(i), "proto/test"
                        ).addCallback(self.process_test_message, i)

    def process_test_message(self, existing_doc, doc_num):
        if existing_doc is None:
            doc = dict(
              storage_key=doc_num,
              )
            self.bulk_docs.append((str(doc_num), doc, 'proto/test'))
        else:
            logger.info("Skipping test message with ID %d - already exists",
                        doc_num)
            # we are done.

    def saved_bulk_messages(self, result, n):
        logger.debug("Finished saving %d test messages in bulk", n)
        # done

# A 'converter' - takes a proto/test as input and creates a
# 'raw/message/rfc822' as output.
class TestConverter(base.ConverterBase):
    def convert(self, doc):
        me = doc['storage_key']
        headers = {'from': 'From: from%(storage_key)d@test.com',
                   'subject' : 'This is test document %(storage_key)d',
        }
        for h in headers:
            headers[h] = headers[h] % doc

        body = u"Hello, this is test message %(storage_key)d (with extended \xa9haracter!)" % doc
        # make an attachment for testing purposes.
        attachments = {"attach1" : {"content_type" : 'application/octet-stream',
                                    "data" : 'test\0blob'
                                    }
                      }
        new_doc = dict(headers=headers, body=body, _attachments=attachments)
        return new_doc


class TestAccount(base.AccountBase):
  def startSync(self, conductor):
    return TestMessageProvider(self, conductor).attach()
