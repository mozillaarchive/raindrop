import itertools

def update_group(group_key, grouping_tags, rd_source):
    # query every conversation with those grouping tags to get the unread
    # ids.
    logger.debug('building summary for grouping %r with tags %s', group_key,
                 grouping_tags)
    results = open_view('raindrop!content!all', 'conv-groupings-with-unread',
                        keys=grouping_tags)
    conv_ids = list(set([hashable_key(row['value']) for row in results['rows']]))
    items = {'unread': conv_ids[:5],
             'num_unread': len(conv_ids)
             }
    emit_schema('rd.grouping.summary', items, rd_key=group_key, rd_source=rd_source)

def update_default_group(rd_source):
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
    update_group(['display-group', None], list(all_tags-grouped_tags), rd_source)
    
def handler(doc):
    rd_source = (doc['_id'], doc['_rev'])
    process_later((doc['all_grouping_tags'], rd_source))

def later_handler(tags_info):
    # first find the unique set of grouping-tags
    all_tags = {}
    for grouping_tags, rd_source in tags_info:
        for gt in grouping_tags:
            all_tags[gt] = rd_source
    logger.debug("all tags are %s", all_tags)
    # Now find the unique set of 'display-group's with those tags
    groups = {}
    seen_tags = set()
    keys = [['rd.grouping.info', 'grouping_tags', gt]
            for gt in all_tags]
    result = open_view(keys=keys, include_docs=True, reduce=False)
    for row in result['rows']:
        # the doc has the group key and the list of grouping_tags
        this_tag = row['key'][-1]
        rd_source = all_tags[this_tag]
        groups[hashable_key(row['value']['rd_key'])] = (row['doc']['grouping_tags'], rd_source)
        seen_tags.add(this_tag)
    # now process them - first the found groups
    for group, (tags, rd_source) in groups.iteritems():
        update_group(group, tags, rd_source)

    if seen_tags != set(all_tags):
        update_default_group(rd_source)
