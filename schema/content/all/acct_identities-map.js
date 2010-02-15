function(doc) {
    if (doc.rd_schema_id=="rd.account") {
        for each (var idty in doc.identities)
            // emit the idid in a list, so a reduce version of the view
            // doesn't depend on how many elements in the key.
            // (ie, with [idty], group_level=1 always returns an idid,
            // whereas with just idty, each idty must be the same length to
            // work.)
            emit([idty], null);
    }
}
