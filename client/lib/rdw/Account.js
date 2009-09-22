dojo.provide("rdw.Account");

dojo.require("rdw._Base");
dojo.require("rd.api");

dojo.declare("rdw.Account", [rdw._Base], {
  templateString: '<div class="rdwAccount" dojoAttachEvent="onclick: onClick"> \
                    <span class="name" dojoAttachPoint="nameNode"></span> \
                    <a class="logout" href="#">&mdash;logout</a> \
                    <a class="settings" href="#rd:account-settings">settings</a> \
                   </div>',

  postCreate: function() {
    //summary: dijit lifecycle method, after template is in the DOM.
    rd.api().me().ok(this, function(idtys) {
      var name = "";
      for (var i = 0, idty; idty = idtys[i]; i++) {
        if (i == 0) {
          name = idty.rd_key[1][1];
        }
        //First identity with a name wins until there is a contact
        //written for all identities.
        if (idty.name) {
          name = idty.name;
          break;
        }
      }
      rd.escapeHtml(name, this.nameNode);
    });
  },

  onClick: function(evt) {
    //summary: handles click events.
    
    //Do not want protocol links going out for this widget.
    var href = evt.target.href;
    if (href && (href = href.split("#")[1])) {
      if (href.indexOf("rd:") == 0) {
        rd.dispatchFragId(href);
        evt.preventDefault();
      }
    }
  }
});
