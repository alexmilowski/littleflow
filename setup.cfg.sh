#!/bin/bash
VERSION=`python -c "import littleflow; print('.'.join(map(str,littleflow.__version__)))"`
AUTHOR=`python -c "import littleflow; print(littleflow.__author__)"`
EMAIL=`python -c "import littleflow; print(littleflow.__author_email__)"`
DESCRIPTION="A little flow language for workflows"
REQUIRES=`python -c "list(map(print,['\t'+line.strip() for line in open('requirements.txt', 'r').readlines()]))"`
cat <<EOF > setup.cfg
[metadata]
name = littleflow
version = ${VERSION}
author = ${AUTHOR}
author_email = ${EMAIL}
description = ${DESCRIPTION}
license = Apache License 2.0
url = https://github.com/alexmilowski/littleflow

[options]
packages =
   littleflow
include_package_data = True
install_requires =
${REQUIRES}

[options.package_data]
* = *.json, *.yaml

EOF
