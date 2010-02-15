def handler(doc):
    logger.debug("source doc is %(_id)r/%(_rev)r", doc)
    if doc['num_syncs'] != 1:
        return
    
    result = open_view(viewId='acct_protocols', key='smtp', include_docs=True)
    rows = result['rows']
    if not rows:
        logger.warn("can't find an smtp account from which to send welcome email")
        return
    acct = rows[0]['doc']

    # check the outgoing state - this isn't strictly necessary as final
    # send will check for us - but it prevents us doing this extra work and
    # giving the impression via the logs that we are doing things multiple
    # times (our souch doc actually changes during the send.)
    if doc.get('outgoing_state') != 'outgoing':
        return

    # write a simple outgoing schema
    addy = acct['username']
    body = 'no really - welcome!  Raindrop just synchronized %d of your messages' % doc['new_items']
    item = {'body' : body,
            'from' : ['email', addy],
            'from_display': 'raindrop',
            'to' : [
                       ['email', addy],
                   ],
            'to_display' : ['you'],
            'subject': "Welcome to raindrop",
    }
    emit_schema('rd.msg.outgoing.simple', item)
    logger.info("queueing welcome mail to '%s'", addy)
