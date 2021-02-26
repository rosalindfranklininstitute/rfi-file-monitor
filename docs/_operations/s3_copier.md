---
layout: default
title: S3 Copier
supported: [S3Object]
---

# S3 Copier

## Purpose

This operation copies objects between S3 buckets hosted in different endpoints and/or regions, and owned by different users.

Before launching a pipeline with this operation, ensure that the IAM user can access the bucket. This can be accomplished by attaching a suitable policy to the bucket:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::<i>accountID</i>:user/<i>IAM-username</i>"
            },
            "Action": "s3:ListBucket",
            "Resource": "arn:aws:s3:::<i>bucket-name</i>"
        },
        {
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::<i>accountID</i>:user/<i>IAM-username</i>"
            },
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::<i>bucket-name</i>/*"
        }
    ]
}
```

Replace <i>accountID</i>, <i>IAM-username</i> and <i>bucket-name</i> with appropriate values.

## Options

* <b>Endpoint</b>: the S3 endpoint to copy to. The field is prepopulated with the default AWS endpoint url. You may also use non-AWS compatible S3 endpoints. Ensure that the url contains the protocol to be used (http or https).
* <b>Verify SSL Certificates</b>: if using an https endpoint with self-signed certificates, the connection may fail due to an SSL exception. Disabling SSL verification may help in this case, but is generally not recommended.
* <b>Access Key</b>: the access key belonging to the IAM user, whose attached policies allow for copying to this bucket.
* <b>Secret Key</b>: the secret key that is associated with the access key.
* <b>Bucket Name</b>: the bucket to copy to. 
* <b>Create bucket if necessary</b>: if checked, then the monitor will try to create it on the endpoint before attempting to copy to it. If not, and the bucket does not exist, copying will not be allowed to start.

## Known Limitations

Currently buckets are created in the default region, which for AWS corresponds to us-east-1 (North Virginia). If this is not desired, please create the bucket manually in the desired region before launching the pipeline.

## Supported File Formats

<b>S3Object</b>

## Author

Tom Schoonjans