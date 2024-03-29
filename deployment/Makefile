VERSION=`python -c "import configparser; p=configparser.ConfigParser(); p.read('../setup.cfg'); print(p['metadata']['version'])"`
REDIS_VERSION=`python -c "import configparser; p=configparser.ConfigParser(); p.read('../integrations/redis/setup.cfg'); print(p['metadata']['version'])"`
PYTHON_VERSION=3.10
ARCH=amd64
ARCHIVE=littleflow-redis-${VERSION}-${REDIS_VERSION}-${PYTHON_VERSION}-${ARCH}.pyz
NAME=test
REPO_URL=https://github.com/alexmilowski/littleflow.git
BRANCH=main
BUCKET=mybucket
BUCKET_PATH=littleflow/
NAMESPACE=littleflow
BUILD_NAMESPACE=build
BUILD_SUFFIX=build
REDIS_HOST=redis-primary.data.svc.cluster.local
REDIS_PORT=6379
REDIS_USERNAME=default
REDIS_PASSWORD=
ARCHIVE_INIT=gcp-init-archive.yaml
NAMESPACE=littleflow
LOG_LEVEL=info

all:
	@echo "Littleflow: ${VERSION}"
	@echo "Littleflow Redis: ${REDIS_VERSION}"
	@echo "Shiv: ${ARCHIVE}"

local-build:
	shiv -o ${ARCHIVE} -e littleflow_redis:main .. ../integrations/redis gunicorn


make-build-storage:
	aws sts get-session-token | python -c "import json, sys; d=json.load(sys.stdin)['Credentials']; s=open('remote-build/template/storage.properties').read(); print(s.format(**d))" > ${NAME}/storage.properties
	
make-build:
	mkdir -p ${NAME}
	aws sts get-session-token | python -c "import json, sys; d=json.load(sys.stdin)['Credentials']; s=open('remote-build/template/storage.properties').read(); print(s.format(**d))" > ${NAME}/storage.properties
	REPO_URL=${REPO_URL} BRANCH=${BRANCH} BUCKET=${BUCKET} BUCKET_PATH=${BUCKET_PATH} ARCH=${ARCH} python -c "import json, os; s=open('remote-build/template/config.properties').read(); print(s.format(**os.environ))" > ${NAME}/config.properties
	NAMESPACE=${BUILD_NAMESPACE} SUFFIX=${BUILD_SUFFIX}-${ARCH} python -c "import os; s=open('remote-build/template/kustomization.yaml').read(); print(s.format(**os.environ))" > ${NAME}/kustomization.yaml
	ARCH=${ARCH} python -c "import os; s=open('remote-build/template/arch.yaml').read(); print(s.format(**os.environ))" > ${NAME}/arch.yaml

run-cloudbuild:
	gcloud builds submit --config=cloudbuild.yaml --no-source --substitutions=_BUCKET=${BUCKET},_BUCKET_PATH=${BUCKET_PATH},_BRANCH_NAME=${BRANCH},_ARCH=${ARCH}

make-deploy:
	mkdir -p ${NAME}/site
	BUCKET=${BUCKET} BUCKET_PATH=${BUCKET_PATH} ARCHIVE=${ARCHIVE} REDIS_HOST=${REDIS_HOST} REDIS_PORT=${REDIS_PORT} LOG_LEVEL=${LOG_LEVEL} python -c "import os; [print(name+'='+os.environ.get(env_name,'')) for name,env_name in [('bucket','BUCKET'),('path','BUCKET_PATH'),('archive','ARCHIVE'),('redis_host','REDIS_HOST'),('redis_port','REDIS_PORT'),('log_level','LOG_LEVEL')]]" > ${NAME}/site/config.properties
	REDIS_USERNAME=${REDIS_USERNAME} REDIS_PASSWORD=${REDIS_PASSWORD} python -c "import os; [print(name+'='+os.environ.get(env_name,'')) for name,env_name in [('username','REDIS_USERNAME'),('password','REDIS_PASSWORD')]]" > ${NAME}/site/redis.properties
	cp site-kustomization.yaml ${NAME}/site/kustomization.yaml
	mkdir -p ${NAME}/receiptlog
	NAMESPACE=${NAMESPACE} DIR=receiptlog python -c "import os; s=open('worker-kustomization.yaml').read(); print(s.format(**os.environ))" > ${NAME}/receiptlog/kustomization.yaml
	cp ${ARCHIVE_INIT} ${NAME}/receiptlog/init.yaml
	mkdir -p ${NAME}/lifecycle
	NAMESPACE=${NAMESPACE} DIR=lifecycle python -c "import os; s=open('worker-kustomization.yaml').read(); print(s.format(**os.environ))" > ${NAME}/lifecycle/kustomization.yaml
	cp ${ARCHIVE_INIT} ${NAME}/lifecycle/init.yaml
	mkdir -p ${NAME}/api
	NAMESPACE=${NAMESPACE} DIR=api python -c "import os; s=open('worker-kustomization.yaml').read(); print(s.format(**os.environ))" > ${NAME}/api/kustomization.yaml
	cp ${ARCHIVE_INIT} ${NAME}/api/init.yaml
	mkdir -p ${NAME}/console
	NAMESPACE=${NAMESPACE} DIR=console python -c "import os; s=open('worker-kustomization.yaml').read(); print(s.format(**os.environ))" > ${NAME}/console/kustomization.yaml
	cp ${ARCHIVE_INIT} ${NAME}/console/init.yaml
