LF_VERSION=`PYTHONPATH=..; python -c 'import littleflow; print(".".join(map(str,littleflow.__version__)))'`
LF_REDIS_VERSION=`PYTHONPATH=..:../integrations/redis; python -c 'import littleflow_redis; print(".".join(map(str,littleflow_redis.__version__)))'`
TARGET=littleflow-redis-${LF_VERSION}-${LF_REDIS_VERSION}.pyz

all:
	@echo "Littleflow: ${LF_VERSION}"
	@echo "Littleflow Redis: ${LF_REDIS_VERSION}"
	@echo "Shiv: ${TARGET}"

local-build:
	shiv -o littleflow-redis-${LF_VERSION}-${LF_REDIS_VERSION}.pyz -e littleflow_redis:main .. ../integrations/redis

remote-build:
