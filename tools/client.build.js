({
    appDir: "../client",
    baseUrl: "./",
    requireUrl: "requirejs/require.js",
    dir: "clientbuild",
    locale: "en-us",

    //Uncomment the next line to turn off Closure Compiler minification.
    optimize: "none",

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
        "require": "../requirejs/require",
        "require/rdCouch": "lib/require/rdCouch"
    },

    pragmas: {
        useStrict: false
    },

    modules: [
        {
            name: "dojo",
            include: [
                "inflow",
                "require/rdCouch",
        
                //START all the extensions. This is assumes user wants all our
                //extensions
                "rdw/ext/debug/ext",
        
                "rdw/ext/facebook/ext",
                "rdw/ext/facebook/Group",
        
                "rdw/ext/feedNotification/ext",
                "rdw/ext/feedNotification/Group",
        
                "rdw/ext/mailingList/ext",
                "rdw/ext/mailingList/model",
                "rdw/ext/mailingList/Summary",
                "rdw/ext/mailingList/SummaryGroup",
                "rdw/ext/mailingList/Group",
        
                "rdw/ext/twitter/ext",
                "rdw/ext/twitter/Conversation",
                "rdw/ext/twitter/Group",
                "rdw/ext/twitter/Message",

                "rdw/ext/MessageLinkAttachments",
                "rdw/ext/MessageLinkImgAttachments",
                "rdw/ext/MessageLinkLocationAttachments",
                "rdw/ext/MessageVimeoLinkAttachments",
                "rdw/ext/metrics",
                "rdw/ext/TwitterMessage",
                "rdw/ext/youTubeMessage"
                //END all the extensions
            ]
        }
    ]
})
