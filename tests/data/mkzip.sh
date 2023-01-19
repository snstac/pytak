#!/usr/bin/env bash

ZIP_NAME=test_pref_package.zip

rm -f ${ZIP_NAME}
zip -r ${ZIP_NAME} *.pref manifest.xml *.p12

