#!/bin/bash
VERSION=`python -c "import littleflow_redis; print('.'.join(map(str,littleflow_redis.__version__)))"`
AUTHOR=`python -c "import littleflow_redis; print(littleflow_redis.__author__)"`
EMAIL=`python -c "import littleflow_redis; print(littleflow_redis.__author_email__)"`
DESCRIPTION=`python -c "import littleflow_redis; print(littleflow_redis.__doc__.strip())"`
REQUIRES=`python -c "list(map(print,['\t'+line.strip() for line in ['littleflow']+open('requirements.txt', 'r').readlines()]))"`
cat <<EOF > setup.cfg
[metadata]
name = littleflow_redis
version = ${VERSION}
author = ${AUTHOR}
author_email = ${EMAIL}
description = ${DESCRIPTION}
license = Apache License 2.0
url = https://github.com/alexmilowski/littleflow

[options]
packages =
   littleflow_redis
include_package_data = True
install_requires =
${REQUIRES}

[options.package_data]
* = *.json, *.yaml

EOF
