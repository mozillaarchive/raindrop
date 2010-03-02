require(
    {
        appDir: "../client",
        baseUrl: "./",
        requireUrl: "requirejs/require.js",
        dir: "clientbuild",
        execModules: false,

        //Uncomment the next line to turn off Closure Compiler minification.
        //optimize: "none",

        //Paths are relative to baseUrl.
        paths: {
            "dojo": "dojo/dojo",
            "dijit": "dojo/dijit",
            "dojox": "dojo/dojox",
            "jquery": "lib/jquery-1.4",
            "inflow": "inflow/inflow",
            "rd": "lib/rd",
            "rdw": "lib/rdw",
            "couch": "lib/couch",
            "require/rdCouch": "lib/require/rdCouch"
        }
    },
    "dojo",
    [
        "inflow",
        "rd/schema",
        "require/rdCouch",
        "i18n!rdw/nls/i18n",

        //START all the extensions. This is assumes user wants all our
        //extensions
        "rdw/ext/debug/ext",

        "rdw/ext/facebook/ext",
        "rdw/ext/facebook/Group",

        "rdw/ext/feedNotification/ext",
        "rdw/ext/feedNotification/Group",

        "rdw/ext/mailingList/ext",
        "rdw/ext/mailingList/model",
        "i18n!rdw/ext/mailingList/nls/i18n",
        "rdw/ext/mailingList/Summary",
        "rdw/ext/mailingList/SummaryGroup",
        "rdw/ext/mailingList/Group",
        "rdw/ext/mailingList/GroupConversation",

        "rdw/ext/twitter/ext",
        "rdw/ext/twitter/Conversation",
        "rdw/ext/twitter/Group",
        "rdw/ext/twitter/Message",

        "rdw/ext/MessageBitlyLinkAttachments",
        "rdw/ext/MessageLinkAttachments",
        "rdw/ext/MessageLinkImgAttachments",
        "rdw/ext/MessageLinkLocationAttachments",
        "rdw/ext/MessageVimeoLinkAttachments",
        "rdw/ext/metrics",
        "rdw/ext/TwitterMessage",
        "rdw/ext/youTubeMessage"
        //END all the extensions
    ]
);
