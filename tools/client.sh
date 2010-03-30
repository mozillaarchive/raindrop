#!/bin/sh

# Remove previous build
rm -rf ./clientbuild

# Get the version to use for the directory.
version=`hg identify -i | sed 's/[^A-Za-z0-9]//'`

# Run the build
# requirejs/build/buildedbug.sh client.build.js
requirejs/build/build.sh client.build.js

