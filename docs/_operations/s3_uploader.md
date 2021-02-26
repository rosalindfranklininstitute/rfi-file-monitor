---
layout: default
title: S3 Uploader
supported: [RegularFile, Directory]
---

# S3 Uploader

## Purpose

This operation allows for uploading the monitored files to an S3 bucket hosted by Amazon Web Services, or any other compatible endpoint (Ceph, MinIO, etc).

## Options

* <b>Endpoint</b>: The S3 endpoint to upload to. The field is prepopulated with the default AWS endpoint url. You may also use non-AWS compatible S3 endpoints. Ensure that the url contains the protocol to be used (http or https).
* <b>Verify SSL Certificates</b>: if using an https endpoint with self-signed certificates, the connection may fail due to an SSL exception. Disabling SSL verification may help in this case, but is generally not recommended.
* <b>Access Key</b>: the access key belonging to the IAM user, whose attached policies allow for uploading to this bucket.
* <b>Secret Key</b>: the secret key that is associated with the access key.
* <b>Bucket Name</b>: the bucket to upload to. 
* <b>Create bucket if necessary</b>: if checked, then the monitor will try to create it on the endpoint before attempting to upload to it. If not, and the bucket does not exist, monitoring will not be allowed to start.

## Known Limitations

Currently buckets are created in the default region, which for AWS corresponds to us-east-1 (North Virginia). If this is not desired, please create the bucket manually in the desired region before launching the pipeline.

## Supported File Formats

<b>RegularFile</b>, <b>Directory</b>

## Author

Tom Schoonjans