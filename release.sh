#!/bin/bash

VERSION=$(cat stravatools/__init__.py | grep __version__ | sed -e "s/__version__.*=.*'\(.*\)'.*/\1/g")

if [ ! -z "$(git status --porcelain)" ]; then 
	echo "Cannot release: uncommitted changes"
	git status --porcelain
	exit 1
fi

if [ -z "$VERSION" ]; then
	echo "Unable to compute version"	
	exit 2
fi

echo rm -f dist/*
echo python setup.py bdist_wheel
echo python -m twine upload dist/*
echo git tag "strava-tools-$VERSION"
echo git push