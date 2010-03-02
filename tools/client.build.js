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
    ["inflow"]
);
