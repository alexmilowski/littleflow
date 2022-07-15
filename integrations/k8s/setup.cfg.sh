#!/bin/bash
VERSION=`python -c "import littleflow_k8s; print('.'.join(map(str,littleflow_k8s.__version__)))"`
AUTHOR=`python -c "import littleflow_k8s; print(littleflow_k8s.__author__)"`
EMAIL=`python -c "import littleflow_k8s; print(littleflow_k8s.__author_email__)"`
DESCRIPTION=`python -c "import littleflow_k8s; print(littleflow_k8s.__doc__.strip())"`
REQUIRES=`python -c "list(map(print,['\t'+line.strip() for line in open('requirements.txt', 'r').readlines()]))"`
cat <<EOF > setup.cfg
[metadata]
name = littleflow_k8s
version = ${VERSION}
author = ${AUTHOR}
author_email = ${EMAIL}
description = ${DESCRIPTION}
license = Apache License 2.0
url = https://github.com/alexmilowski/littleflow

[options]
packages =
   littleflow_k8s
include_package_data = True
install_requires =
${REQUIRES}

[options.package_data]
* = *.json, *.yaml

EOF
