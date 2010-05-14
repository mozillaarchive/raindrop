# A smart 'attachment summary' processor - as it sees schemas which relate
# to attachments, it arranges to write an 'attachment-summary' schema which
# summaries all attachments and all their schema-ids for a specific message.
import itertools

import raindrop.model
split_doc_id = raindrop.model.DocumentModel.split_doc_id

# We declare 'null' for our source schemas, therefore we are expected to
# provide a filter function to see which ones we care about.
def filter(src_id, src_rev, schema_id):
    try:
        _, rd_key, _ = split_doc_id(src_id)
    except ValueError:
        # malformed doc - ignore it
        return False
    # we want any which relate to attachments.
    return rd_key[0] == 'attach'

def handler(doc):
    # extract the rd_key of the message itself and say we want to be
    # called later with all the keys
    msg_key = doc['rd_key'][1][0]
    rd_source = [doc['_id'], doc['_rev']]
    process_later((msg_key, rd_source))

def later_handler(pending):
    key_sources = {}
    for key, rd_source in pending:
        key_sources[hashable_key(key)] = rd_source
    all_keys = key_sources.keys()
    # find any existing summary documents for the keys.
    schema_id = 'rd.msg.attachment-summary'
    all_existing = {}
    existing = open_schemas([[k, schema_id] for k in all_keys])
    for k, e in zip(all_keys, existing):
        if e is not None:
            all_existing[k] = e

    # perform the query for the attachments.
    result = open_view(viewId="attach_by_owned_key", keys=all_keys)
    for msg_key, key_items in itertools.groupby(result['rows'],
                                                lambda r: r['key']):
        # build a dict keyed by attachment key.
        attach_dict = {}
        for item in key_items:
            attach_key = hashable_key(item['value']['rd_key'])
            attach_info = attach_dict.setdefault(attach_key, [])
            attach_info.append(item['value']['rd_schema_id'])
        # and back into the sorted list suitable for json (sorted so we
        # can reliably check if we need to write a new value)
        attachments = []
        for attach_key in sorted(attach_dict.iterkeys()):
            schemas = sorted(attach_dict[attach_key])
            attachments.append({'id': attach_key, 'schemas': schemas})

        schema = {'attachments': attachments}
        try:
            existing = all_existing[hashable_key(key)]
        except KeyError:
            pass
        else:
            if existing['attachments'] == attachments:
                continue
            schema['_rev'] = existing['_rev']
        rd_source = key_sources[hashable_key(msg_key)]
        emit_schema(schema_id, schema, rd_key=msg_key, rd_source=rd_source)
