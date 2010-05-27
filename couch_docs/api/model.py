# The classes which define the API; all methods without a leading _ are public
class ContactsAPI(API):
    def create_identity_relationships(self, req):
        self.requires_get_or_post(req)
        args = self.get_args(req, 'contact_properties', 'relationships',
                             ext_id="rd.api")
        db = RDCouchDB(req)
        # items_from_related_identities must be moved!
        from raindrop.extenv import items_from_related_identities
        gen = items_from_related_identities(db.doc_model, args['relationships'],
                                            args['contact_properties'],
                                            args['ext_id'])
        return db.doc_model.create_schema_items(list(gen))


class SchemasAPI(API):
    def create_items(self, items):
        self.requires_get_or_post(req)
        args = self.get_args(req, 'items')
        db = RDCouchDB(req)
        return db.doc_model.create_schema_items(args['items'])


# A mapping of the 'classes' we expose.  Each value is a class instance, and
# all 'public' methods (ie, those without leading underscores) on the instance
# are able to be called.
dispatch = {
    'contacts': ContactsAPI(),
    'schemas': SchemasAPI(),
}

# The standard raindrop extension entry-point (which is responsible for
# exposing the REST API end-point) - so many points!
def handler(request):
    return api_handle(request, dispatch)
