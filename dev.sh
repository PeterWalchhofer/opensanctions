#!/bin/sh
cd opensanctions
source env.sh
cd ..
yes | pip3 uninstall opensanctions
pip3 install .
memorious --debug --no-cache run at_poi
