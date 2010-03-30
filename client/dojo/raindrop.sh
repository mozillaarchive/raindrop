#!/bin/sh

rm -rf ./raindropbuild/
../build.sh raindrop.build.js
cp raindrop.build.js ~/hg/raindrop/client/dojo/raindrop.build.js
cp raindrop.sh ~/hg/raindrop/client/dojo/raindrop.sh

cp ./raindropbuild/dojo.js ~/hg/raindrop/client/dojo/dojo.js
cp ./dojorequire/dojo/resources/blank.gif ~/hg/raindrop/client/dojo/dojo/resources/blank.gif
cp ./dojorequire/dijit/themes/dijit.css ~/hg/raindrop/client/dojo/dijit/themes/dijit.css
