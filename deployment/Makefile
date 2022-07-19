LF_VERSION=`PYTHONPATH=..; python -c 'import littleflow; print(".".join(map(str,littleflow.__version__)))'`
LF_REDIS_VERSION=`PYTHONPATH=..:../integrations/redis; python -c 'import littleflow_redis; print(".".join(map(str,littleflow_redis.__version__)))'`
TARGET=littleflow-redis-${LF_VERSION}-${LF_REDIS_VERSION}.pyz
NAME=test
REPO_URL=https://github.com/alexmilowski/littleflow.git
BRANCH=main
BUCKET=mybucket
BUCKET_PATH=littleflow/
NAMESPACE=littleflow
BUILD_NAMESPACE=build
BUILD_SUFFIX=build
ARCH=amd64

all:
	@echo "Littleflow: ${LF_VERSION}"
	@echo "Littleflow Redis: ${LF_REDIS_VERSION}"
	@echo "Shiv: ${TARGET}"

local-build:
	shiv -o littleflow-redis-${LF_VERSION}-${LF_REDIS_VERSION}.pyz -e littleflow_redis:main .. ../integrations/redis


make-build:
	mkdir -p ${NAME}
	aws sts get-session-token | python -c "import json, sys; d=json.load(sys.stdin)['Credentials']; s=open('remote-build/template/storage.properties').read(); print(s.format(**d))" > ${NAME}/storage.properties
	REPO_URL=${REPO_URL} BRANCH=${BRANCH} BUCKET=${BUCKET} BUCKET_PATH=${BUCKET_PATH} ARCH=${ARCH} python -c "import json, os; s=open('remote-build/template/config.properties').read(); print(s.format(**os.environ))" > ${NAME}/config.properties
	NAMESPACE=${BUILD_NAMESPACE} SUFFIX=${BUILD_SUFFIX}-${ARCH} python -c "import os; s=open('remote-build/template/kustomization.yaml').read(); print(s.format(**os.environ))" > ${NAME}/kustomization.yaml
	ARCH=${ARCH} python -c "import os; s=open('remote-build/template/arch.yaml').read(); print(s.format(**os.environ))" > ${NAME}/arch.yaml
