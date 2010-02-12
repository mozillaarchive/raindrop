import itertools

def update_group(group_key, grouping_tags):
    # query every conversation with those grouping tags to get the unread
    # ids.
    results = open_view('raindrop!content!all', 'conv-groupings-with-unread',
                        keys=grouping_tags)
    for gt, conv_rows in itertools.groupby(results['rows'], lambda row: row['key']):
        conv_ids = list(set([hashable_key(row['value']) for row in conv_rows]))
        items = {'unread': conv_ids[:5],
                 'num_unread': len(conv_ids)
                 }
        emit_schema('rd.grouping.summary', items, rd_key=group_key)

def update_default_group():
    # get the list of grouping tags in groupings
    grouped_tags = set()
    key = ['rd.core.content', 'schema_id', 'rd.grouping.info']
    result = open_view(key=key, include_docs=True, reduce=False)
    for row in result['rows']:
        for tag in row['doc']['grouping_tags']:
            grouped_tags.add(tag)
    # now get the set of all tags in all messages.
    skey = ['rd.msg.grouping-tag', 'tag']
    ekey = ['rd.msg.grouping-tag', 'tag', {}]
    result = open_view(startkey=skey, endkey=ekey, group_level=3)
    all_tags = set(r['key'][-1] for r in result['rows'])
    update_group(['display-group', None], list(all_tags-grouped_tags))
    

def handler(doc):
    need_default = False
    for gt in doc['groups_with_unread']:
        # find the 'display-group's with those tags
        key = ['rd.grouping.info', 'grouping_tags', gt]
        result = open_view(key=key, include_docs=True, reduce=False)
        if not result['rows']:
            need_default = True
        else:
            for row in result['rows']:
                # the doc has the group key and the list of grouping_tags
                update_group(row['doc']['rd_key'], row['doc']['grouping_tags'])
    if need_default:
        update_default_group()
