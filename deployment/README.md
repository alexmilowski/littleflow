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

And then copy them to S3:

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


## OPTIONAL: Setup AWS S3 credentials for pulling

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

## OPTIONAL: Setup a GCP identity 

Once you have a GCP Service Account private key credential, you can use a secret for pulling resources:

The service account key is stored in a secret

```
kubectl create secret generic issuer --from-file=identity.json
```

where `identity.json` is the private key for the GCP credentials. A similar
technique can be use for AWS.
 
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
 * `ARCHIVE_INIT` The archive intitialization template (e.g., `aws-init-archive.yaml`, `gcp-init-archive.yaml`, or `remote-init-archive.yaml` - defaults to `gcp-init-archive.yaml`)

Build the kustomization:

```
NAME=test-deploy BUCKET=test-littleflow REDIS_HOST=myredis.data.svc.cluster.local make -e make-deploy
```

Make sure you have the `littleflow` service account:

```
kubectl apply -f account.yaml
```

Then deploy the workers, api, and console:

```
NAME=test-deploy
kubectl apply -k ${NAME}/lifecycle
kubectl apply -k ${NAME}/receiptlog
kubectl apply -k ${NAME}/api
kubectl apply -k ${NAME}/console
```

The ARCHIVE_INIT is used to configure where the shiv archive is retrieved. This is typically a bucket stored in S3 or GCP Cloud Storage. The examples have the following roles:

 * Use [aws-init-archive.yaml](aws-init-archive.yaml) to pull from S3 using credentials in a secret
 * Use [gcp-init-archive.yaml](gcp-init-archive.yaml) to pull from GCP Cloud storage using something like Workload Identity
 * Use [remote-init-archive.yaml](remote-init-archive.yaml) as an example to pull from a completed remote cluster (e.g., an on-prem cluster). This example shows how to use a google service account key.

