#!/bin/sh

# Remove previous build
rm -rf ./clientbuild

# Make sure Dojo is unzipped since we want to include it
if [ ! -d ../client/dojo ]; then
    echo "Unzipping Dojo"
    cd ../client
    unzip dojo.zip
    cd ../tools
fi

# Get the version to use for the directory.
version=`hg identify -i | sed 's/[^A-Za-z0-9]//'`

# Run the build
# requirejs/build/buildedbug.sh client.build.js
requirejs/build/build.sh client.build.js

# Zip up the new dojo directory.
cd clientbuild
rm dojo.zip
zip -r dojo.zip dojo/*
rm -rf ./dojo/
cd ..

