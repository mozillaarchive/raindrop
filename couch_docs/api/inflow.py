# ***** BEGIN LICENSE BLOCK *****
# * Version: MPL 1.1
# *
# * The contents of this file are subject to the Mozilla Public License Version
# * 1.1 (the "License"); you may not use this file except in compliance with
# * the License. You may obtain a copy of the License at
# * http://www.mozilla.org/MPL/
# *
# * Software distributed under the License is distributed on an "AS IS" basis,
# * WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# * for the specific language governing rights and limitations under the
# * License.
# *
# * The Original Code is Raindrop.
# *
# * The Initial Developer of the Original Code is
# * Mozilla Messaging, Inc..
# * Portions created by the Initial Developer are Copyright (C) 2009
# * the Initial Developer. All Rights Reserved.
# *
# * Contributor(s):
# *

# This is the 'inflow' REST API implementation.  Note many globals come
# via (and this script must be run via) raindrop-apirunner.py.

import itertools

# The classes which define the API; all methods without a leading _ are public
class ConversationAPI(API):
    def _filter_known_identities(self, db, idids):
        # Given a list/set of identity IDs, return those 'known' (ie, associated
        # with a contact.
        result = db.megaview(key=["schema_id", "rd.identity.contacts"],
                             reduce=False, include_docs=False)
        # Cycle through each document. The rd_key is the full identity ID, we just
        # need the second part of it. It has an array of contacts but each item
        # in the contacts array has other info about the contact, we just need
        # the first part, the contactId.
        all_known = set()
        for row in result['rows']:
            idty = row['value']['rd_key'][1]
            idkey = hashable_key(idty)
            all_known.add(idkey)
        # now return the union.
        return all_known.intersection(set(idids))

    def _fetch_messages(self, db, msg_keys, schemas):
        # Generate proper key for megaview lookup.
        if not schemas:
            # return empty dicts for each key.
            for _ in msg_keys:
                yield {}, {}
            return
        # open_schemas is much faster than a key-schema_id view, so use
        # that if we can.
        elif schemas == ['*']:
            keys = [['key', k] for k in msg_keys]
            result = db.megaview(keys=keys, include_docs=True, reduce=False)
            item_gen = itertools.groupby(
                                (r['doc'] for r in result['rows']),
                                key=lambda d: d['rd_key'])
        else:
            wanted = ((k, sid) for k in msg_keys for sid in schemas)
            result = db.doc_model.open_schemas(wanted)
            item_gen = itertools.groupby((r for r in result if r is not None),
                                         key=lambda d: d['rd_key'])
        message_results = {}
        from_map = {}
        # itertools.groupby rocks :)
        for (rd_key, dociter) in item_gen:
            # Make a dict based on rd_schema_id.
            bag = {}
            for doc in dociter:
                # Make sure we have the right aggregate to use for this row.
                rd_key = doc['rd_key']
                schema_id = doc['rd_schema_id']
                if schemas != ['*'] and schema_id not in schemas:
                    continue

                # Skip some schemas since it is extra stuff we do not need.
                # Prefer a blacklist vs. a whitelist, since user extensions may add
                # other things, and do not want to have extensions register extra stuff? TODO.
                if '.rfc822' in schema_id or '.raw' in schema_id:
                    continue
                # Remove all special raindrop and couch fields.
                for name, val in doc.items():
                    if name.startswith('rd_') or name.startswith('_'):
                        del doc[name]

                assert schema_id not in bag, bag
                bag[schema_id] = doc
            try:
                body = bag['rd.msg.body']
            except KeyError:
                pass
            else:
                frm = body.get('from')
                if frm:
                    # Hold on to the from names to check if they are known later
                    # TODO: this should probably be a back end extension.
                    # TODO: fix the above comment - this kinda *is* a back-end extension :)
                    from_key = hashable_key(frm)
                    from_map.setdefault(from_key, []).append(bag)

            message_results[hashable_key(rd_key)] = bag

        # Look up the IDs for the from identities. If they are real
        # identities, synthesize a schema to represent this.
        # TODO: this should probably be a back-end extension.
        # TODO: as above, fix the above comment :)

        # Cycle through the identities, and work up a schema for
        # them if they are known.
        if schemas==['*'] or 'rd.msg.ui.known' in schemas:
            idtys = self._filter_known_identities(db, from_map)
            for idty in idtys:
                bags = from_map[idty]
                for bag in bags:
                    bag["rd.msg.ui.known"] = {
                        "rd_schema_id" : "rd.msg.ui.known"
                    }
        # now open the 'attachment summary' docs for each of the requested keys.
        wanted_ids = []
        for rd_key in msg_keys:
            si = {'rd_key': rd_key,
                  'rd_schema_id': 'rd.msg.attachment-summary'}
            wanted_ids.append(get_doc_id_for_schema_item(si))
        attach_query = db.allDocs(wanted_ids, include_docs=True)
        
        # it is very important we keep the result list parallel with the
        # input keys, so the caller can match things up correctly.
        for rd_key, attach_row in zip(msg_keys, attach_query['rows']):
            try:
                bag = message_results[hashable_key(rd_key)]
            except KeyError:
                bag = {}
            if 'doc' in attach_row:
                attachments = attach_row['doc']['attachments']
            else:
                attachments = None
            yield (bag, attachments)

    def _build_conversations(self, db, conv_summaries, message_limit, schemas=None):
        # Takes a list of rd.conv.summary schemas and some request args,
        # and builds a list of conversation objects suitable for the result
        # of the API call.
        if not conv_summaries:
            return []

        # Note that the conversation summary doc has summaries for the first
        # 3 messages.  If the caller wants the more than that, or wants
        # specific schemas, we must hit the couch.
        if schemas is None and message_limit is not None:
            for cs in conv_summaries:
                if message_limit > len(cs['messages']) and len(cs['message_ids']) > len(cs['messages']):
                    fetch_schemas = True
                    # but they haven't said *what* schemas - so return the same
                    # schemas we provide in the summaries
                    if cs['messages']:
                        schemas = cs['messages'][0]['schemas'].keys()
                    break
            else:
                # we have everything we need without fetching
                fetch_schemas = False
        else:
            # schemas explicitly specified or unlimited msgs - must fetch them.
            fetch_schemas = True

        # xform the raw convo objects and build a list of msg_ids we need to fetch
        ret = []
        msg_keys = []
        convs_for_msg_keys = []
        for cs in conv_summaries:
            rdkey = cs['rd_key']
            ret_conv = self._filter_user_fields(cs)
            ret_conv['id'] = rdkey
            ret.append(ret_conv)
            if fetch_schemas:
                these_ids = cs['message_ids']
                if message_limit is not None:
                    these_ids = these_ids[:message_limit]
                    ret_conv['messages'] = ret_conv['messages'][:message_limit]
                msg_keys.extend(these_ids)
                convs_for_msg_keys.extend([ret_conv] * len(these_ids))
            else:
                if message_limit is not None:
                    ret_conv['messages'] = ret_conv['messages'][:message_limit]

        # If we are fetching schemas then we update the 'messages'
        # element accordingly.
        if fetch_schemas:
            assert msg_keys # how can we end up with no keys here?
            message_gen = self._fetch_messages(db, msg_keys, schemas)
            # The message_infos are in the exact order of the messages of
            # each convo - so loop in that order taking a message at a time.
            last_conv = None
            for conv, msg_id in zip(convs_for_msg_keys, msg_keys):
                if conv is not last_conv:
                    last_conv = conv
                    msg_index = 0
                else:
                    msg_index += 1
                if msg_index < len(conv['messages']):
                    # a 'summary' already exists, so update that.
                    message = conv['messages'][msg_index]
                else:
                    # this is a message without a summary, so add a new one.
                    message = {'id': msg_id, 'schemas': {}}
                    conv['messages'].append(message)
                new_schemas, new_attach = message_gen.next()
                message['schemas'].update(new_schemas)
                if new_attach:
                    message['attachments'] = new_attach
        return ret

    # The 'single' end-point for getting a single conversation.
    def by_id(self, req):
        self.requires_get(req)
        args = self.get_args(req, 'key', message_limit=None, schemas=None)
        db = RDCouchDB(req)
        conv_id = args["key"]
        log("conv_id: %s", conv_id)
        # get the document holding the convo summary.
        sum_doc = db.doc_model.open_schemas([(conv_id, 'rd.conv.summary')])[0]
        if sum_doc is None:
            return None
        return self._build_conversations(db, [sum_doc], args['message_limit'],
                                         args['schemas'])[0]

    # Fetch all conversations which have the specified messages in them.
    def with_messages(self, req):
        self.requires_get_or_post(req)
        args = self.get_args(req, 'keys', message_limit=None,
                             schemas=None)
        db = RDCouchDB(req)
        return self._with_messages(db, args['keys'], args['message_limit'],
                                   args['schemas'])

    def _with_messages(self, db, msg_keys, message_limit, schemas):
        # make a megaview request to determine the convo IDs with the messages.
        # XXX - note we could maybe avoid include_docs by using the
        # 'message_ids' field on the conv_summary doc - although that will not
        # list messages flaged as 'deleted' etc.
        wanted = ((mid, 'rd.msg.conversation') for mid in msg_keys)
        result = db.doc_model.open_schemas(wanted)
        conv_ids = set()
        for doc in result:
            if result is not None:
                conv_ids.add(hashable_key(doc['conversation_id']))

        # open the conv summary docs.
        wanted = ((conv_id, 'rd.conv.summary') for conv_id in conv_ids)
        result = db.doc_model.open_schemas(wanted)
        # now make the conversation objects.
        docs = [r for r in result if r is not None]
        return self._build_conversations(db, docs, message_limit, schemas)

    # Fetch all conversations which include a message from the specified contact
    def contact(self, req):
        self.requires_get(req)
        args = self.get_args(req, "id", message_limit=None, limit=None, schemas=None, skip=0)
        cid = args['id']
        if cid[0] != "contact":
            raise APIErrorResponse(400, "invalid contact ID: %s" % (cid,))
        db = RDCouchDB(req)
        capi = ContactsAPI()
        idids = capi._fetch_identies_for_contact(db, cid)
        if not idids:
            return []
        return self._identities(db, idids, args)

    # Fetch all conversations which include a message from the specified contact
    def identities(self, req):
        # fetch messages 'from' any of those identities
        # XXX - shouldn't we do 'to' etc too?
        db = RDCouchDB(req)
        self.requires_get(req)
        args = self.get_args(req, ids=None, message_limit=3, schemas=None, limit=30, skip=0)
        ids = args['ids']
        if ids is None:
            # special case - means "my identity".  Note this duplicates code
            # in raindrop/extenv.py's get_my_identities() function.
            result = db.view('raindrop!content!all/acct_identities',
                             group=True, group_level=1)
            mine = set()
            for row in result['rows']:
                iid = row['key'][0]
                mine.add(hashable_key(iid))
            ids = list(mine)
        return self._identities(db, ids, args)

    def _identities(self, db, idids, args):
        result = db.view('raindrop!content!all/conv_summary_by_identity',
                         keys=idids, limit=args['limit'], skip=args['skip'])
        conv_doc_ids = set(r['id'] for r in result['rows'])
        result = db.allDocs(keys=list(conv_doc_ids), include_docs=True)
        # filter out deleted etc.
        docs = [row['doc'] for row in result['rows'] if 'doc' in row]
        convos = self._build_conversations(db, docs, args['message_limit'], args['schemas'])
        convos.sort(key=lambda item: item['messages'][0]['schemas']['rd.msg.body']['timestamp'],
                   reverse=True)
        return convos

    # Helper for most other end-points
    def in_groups(self, req):
        opts = {
            'include_docs': True,
            'descending': True,
        }
        self.requires_get_or_post(req)
        args = self.get_args(req, 'keys', limit=30, skip=0, message_limit=None,
                             schemas=None)
        opts['limit'] = args['limit']
        opts['skip'] = args['skip']
        db = RDCouchDB(req)

        convo_summaries = []
        for gk in args['keys']:
            result = db.view('raindrop!content!all/conv_summary_by_grouping_timestamp',
                             startkey=[gk, {}], endkey=[gk], **opts)
            convo_summaries.extend(row['doc'] for row in result['rows'])

        convos = self._build_conversations(db, convo_summaries, args['message_limit'],
                                           args['schemas'])
        # results are already sorted!
        return convos

    # The 'simpler' end-points based around self._query()
    # XXX - these must die!
    def direct(self, req):
        req['body'] = json.dumps({'keys': [('display-group', 'inflow')]})
        return self.in_groups(req)

    def group(self, req):
        req['body'] = json.dumps({'keys': [('display-group', 'inflow')]})
        return self.in_groups(req)

    def broadcast(self, req):
        req['body'] = json.dumps({'keys': [('display-group', None)]})
        return self.in_groups(req)

    def personal(self, req):
        req['body'] = json.dumps({'keys': [('display-group', 'inflow')]})
        return self.in_groups(req)


class ContactsAPI(API):
    def by_name(self, req):
        self.requires_get(req)
        args = self.get_args(req, startname=None, endname=None, skip=0, limit=None)
        view_args = {}
        if args['startname'] is not None:
            view_args['startkey'] = args['startname']
        if args['endname'] is not None:
            view_args['endkey'] = args['endname']
        if args['skip'] is not None:
            view_args['skip'] = args['skip']

        db = RDCouchDB(req)
        result = db.view('raindrop!content!all/contact_name', **view_args)
        ret = []
        for row in result['rows']:
            this = {'id': row['value']['rd_key'],
                    'displayName': row['key'],
                    }
            ret.append(this)
        return ret
        
    def with_identity(self, req):
        self.requires_get(req)
        args = self.get_args(req, 'id')
        db = RDCouchDB(req)
        result = db.view('raindrop!content!all/contacts_by_identity', key=args['id'])
        ret = []
        for row in result['rows']:
            this = {}
            this['id'] = ["contact", row['value'][0]]
            this['relationship'] = row['value'][1]
            ret.append(this)
        return ret

    def _fetch_identies_for_contact(self, db, cid):
        # find all identity-ids for the contact
        # This view only has the uuid portion of the contact ID.
        startkey = [cid[1]]
        endkey = [cid[1], {}]
        result = db.view('raindrop!content!all/identities_by_contact',
                         startkey=startkey, endkey=endkey)
        ret = []
        for row in result['rows']:
            # the rd_key should be ['identity', idid]
            rdkey = row['value']['rd_key']
            if (rdkey[0] == 'identity'):
                assert len(rdkey)==2
                ret.append(rdkey[1])
            else:
                log("contact has non-identity record: %s", row)
        return ret

class AttachmentAPI(API):
    def by_id(self, req):
        self.requires_get_or_post(req)
        args = self.get_args(req, 'keys', 'schemas', limit=30)
        # XXX - limit not used!  What exactly is it trying to limit?
        # We can do this without a query by calculating the doc IDs.
        wanted_ids = []
        wanted_details = []
        for akey in args['keys']:
            for sid in args['schemas']:
                si = {'rd_key': akey,
                      'rd_schema_id': sid}
                wanted_ids.append(get_doc_id_for_schema_item(si))
                wanted_details.append(si)
        db = RDCouchDB(req)
        result = db.allDocs(wanted_ids, include_docs=True)
        # turn the result into a dict so we can detect missing ones etc.
        by_key = {}
        for row, si in zip(result['rows'], wanted_details):
            if 'doc' in row:
                schemas = by_key.setdefault(hashable_key(si['rd_key']), {})
                schemas[si['rd_schema_id']] = self._filter_user_fields(row['doc'])

        # now back to the 'result' object.
        result = []
        for akey in args['keys']:
            this = {'id': akey,
                    'schemas': {}}
            try:
                found = by_key[hashable_key(akey)]
            except KeyError:
                pass
            else:
                this['schemas'] = found
            result.append(this)
        return result


class GroupingAPI(API):
    def summary(self, req):
        self.requires_get(req)
        db = RDCouchDB(req)
        # Note there might be lots of .info groups, but only a small number
        # of them with 'summary'
        key = ['schema_id', 'rd.grouping.summary']
        result = db.megaview(key=key, include_docs=True, reduce=False)
        by_key = {}
        wanted = []
        for row in result['rows']:
            rd_key = row['value']['rd_key']
            by_key[hashable_key(rd_key)] = row['doc']
            wanted.append((rd_key, 'rd.grouping.info'))
        result = db.doc_model.open_schemas(wanted)
        for doc in result:
            if doc is not None:
                by_key[hashable_key(doc['rd_key'])].update(doc)
        return by_key.values()

class AccountAPI(API):
    def _get_cfg_filename(self, req):
        dbname = req['path'][0]
        return "~/." + dbname
        
    def set(self, req):
        self.requires_post(req)
        body = req.get('body')
        if not body or body == 'undefined':
            raise APIErrorResponse(400, "account ID not specified")
        del req['body'] # so get_args doesn't look in it.
        args = self.get_args(req, 'id')
        items = json.loads(body)

        # now do the work.
        from raindrop.config import Config
        cfg = Config(self._get_cfg_filename(req))
        acct_id = cfg.ACCOUNT_PREFIX + args['id']
        cfg.save_account(acct_id, items)
        return "ok"

    def list(self, req):
        self.requires_get(req)
        args = self.get_args(req)
        dbname = req['path'][0]
        cfg_file = "~/." + dbname

        from raindrop.config import Config
        cfg = Config(cfg_file)
        ret = []
        for raw_acct in cfg.accounts.itervalues():
            acct = raw_acct.copy()
            # anything with certain words in the name get replaced with true to
            # indicate we have something, but not what it is.
            for name, val in acct.items():
                for black in ['password', 'token', 'secret']:
                    if black in name:
                        acct[name] = True
            ret.append(acct)
        return ret


# A mapping of the 'classes' we expose.  Each value is a class instance, and
# all 'public' methods (ie, those without leading underscores) on the instance
# are able to be called.
dispatch = {
    'contacts': ContactsAPI(),
    'conversations': ConversationAPI(),
    'attachments': AttachmentAPI(),
    'grouping' : GroupingAPI(),
    'account' : AccountAPI(),
}

# The standard raindrop extension entry-point (which is responsible for
# exposing the REST API end-point) - so many points!
def handler(request):
    return api_handle(request, dispatch)
