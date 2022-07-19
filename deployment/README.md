# Deployment

## Build shiv archive

This deployment uses [shiv archives](https://github.com/linkedin/shiv) to
package the python applications. These archives are pushed to an S3-compatible
service. The deployments will use the archives to run various services.

The archives can be built locally and pushed to S3 manually. Just build
the archives:


```
make local-build
```

And then copt them to S3:

```
aws s3 cp *.pyz s3://mybucket/littleflow/
```

Alternatively, you can build them on a cluster. This is particularly helpful
to build archives cross architectures (e.g., building amd64 vs arm64).

First build the kustomization:

```
NAME=test-build BUCKET=mybucket make -e make-build
```

Then you can check the kustomization:

```
kubectl kustomize test-build
```

Or submit the build:

```
kubectl apply -k test-build
```

The build job will copy the shiv archive to S3 at the very end.


## Setup AWS S3 credentials for pulling

Unless your artifact release bucket is public, you must provide credentials to
access your bucket:

Your `config` file should be something like:

```
[default]
region = us-west-2
```

And your `credentials` file:

```
[default]
aws_access_key_id=...
aws_secret_access_key=...
```

Then you can do:

```
kubectl create secret generic aws --from-file=aws-config=config --from-file=aws-credentials=credentials
```

## Create the deployment account

```
kubectl apply -f account.yaml
```

## Make the deployment configuration

Variables to set:

 * `NAME` The name of the local directory for kustomize (defaults to `test`)
 * `BUCKET` The name of the bucket for the shiv archive
 * `BUCKET_PATH` The path in the bucket for the archive (defaults to `littleflow/`)
 * `VERSION` The littleflow version (defaults to latest)
 * `REDIS_VERSION` The littleflow redis version (defaults to latest)
 * `REDIS_HOST` The redis host to use (defaults to `redis-primary.data.svc.cluster.local`)
 * `REDIS_PORT` The redis port (defaults to 6379)
 * `REDIS_USERNAME` The redis user (defaults to `default`)
 * `REDIS_PASSWORD` The redis password (no default)

Build the kustomization:

```
NAME=test-deploy BUCKET=test-littleflow REDIS_HOST=myredis.data.svc.cluster.local make -e make-deploy
```

Then deploy the receiptlog and lifecycle workers:

```
kubectl apply -k test-deploy/lifecycle
kubectl apply -k test-deploy/receiptlog
```
