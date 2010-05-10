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

# The outgoing SMTP protocol for raindrop.
from __future__ import with_statement

import sys
import smtplib
import base64

from ..proc import base
from . import xoauth

import logging
logger = logging.getLogger(__name__)


class SMTPAccount(base.AccountBase):
    rd_outgoing_schemas = ['rd.msg.outgoing.smtp']

    def doSend(self, src_doc, out_doc):
        dm = self.doc_model
        adfrom = out_doc['smtp_from']
        adto = out_doc['smtp_to']
        details = self.details
        acct = self
        # Here we record the fact we have attempted an SMTP send and
        # save the state back now - this should cause conflict errors if we
        # accidently have 2 processes trying to send the same message.
        self._update_sent_state(src_doc, 'sending')
        do_oauth = False
        try:
            # open the attachment.
            aname, _ = dm.get_schema_attachment_info(out_doc,
                                                     'smtp_body')
            attach = dm.db.openDoc(dm.quote_id(out_doc['_id']),
                                   attachment=aname)
            # Now establish the connection
            server = smtplib.SMTP(details['host'], details['port'])

            # note that gmail doesn't report it supports 'auth' until you
            # have switched to TLS mode - and we need it to report it else
            # server.login() aborts without even trying!
            try:
                server.starttls()
            except smtplib.SMTPException:
                logger.info("smtp server does not support TLS")
            server.ehlo_or_helo_if_needed()

            if server.has_extn("auth"):
                # Authentication methods the server supports:
                authlist = server.esmtp_features["auth"].split()
                do_oauth = 'XOAUTH' in authlist
                if do_oauth:
                    if not xoauth.AcctInfoSupportsOAuth(details):
                        logger.warn("This server supports OAUTH but no tokens or secrets are available to use - falling back to password")
                        do_oauth = False
                if do_oauth:
                    xoauth_string = xoauth.GenerateXOauthStringFromAcctInfo('smtp', details)
                    server.docmd('AUTH', 'XOAUTH ' + base64.b64encode(xoauth_string))
                elif 'username' in details and 'password' in details:
                    logger.info("logging into smtp server using password")
                    server.login(details['username'], details['password'])
                else:
                    logger.info('server supports authentication but no credentials are known')
            else:
                logger.info("smtp server doesn't support authentication.")

            server.sendmail(adfrom, adto, attach)
            logger.info("smtp mail sent.")
            server.quit()
        except smtplib.SMTPResponseException, exc:
            # for now, reset 'outgoing_state' back to 'outgoing' so the
            # next attempt retries.  We should differentiate between
            # 'permanent' errors and others though...
            self._update_sent_state(src_doc, 'error',
                                    exc.smtp_code, exc.smtp_error,
                                    outgoing_state='outgoing')
            if exc.smtp_code==535:
                why = acct.OAUTH if do_oauth else acct.PASSWORD 
                acct.reportStatus(what=acct.ACCOUNT, state=acct.BAD, why=why,
                               message=exc.smtp_error)
            else:
                acct.reportStatus(what=acct.SERVER, state=acct.BAD, why=acct.REJECTED,
                               message=exc.smtp_error)
            raise
        except Exception, exc:
            self._update_sent_state(src_doc, 'error',
                                    outgoing_state='outgoing')
            acct.reportStatus(what=acct.ACCOUNT, state=acct.BAD,
                              message=str(exc))
            raise
        else:
            self._update_sent_state(src_doc, 'sent')
            acct.reportStatus(what=acct.EVERYTHING, state=acct.GOOD)

    def startSend(self, conductor, src_doc, out_doc):
        def on_failed(exc):
            if not isinstance(exc, (smtplib.SMTPConnectError, smtplib.SMTPHeloError)):
                raise

        # do it...
        assert src_doc['outgoing_state'] == 'outgoing', src_doc # already sent?
        try:
            conductor.apply_with_retry(self, on_failed, self.doSend, src_doc, out_doc)
        except smtplib.SMTPException, exc:
            logger.error("error sending SMTP message: %s" % (exc,))
        except Exception:
            logger.exception("failed to send SMTP message")

    def get_identities(self):
        username = self.details.get('username')
        if '@' not in username:
            logger.warning("SMTP account username isn't an email address - can't guess your identity")
            return []
        return [('email', username)]
