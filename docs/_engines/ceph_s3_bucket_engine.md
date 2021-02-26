---
layout: default
title: Ceph S3 Bucket Monitor
exported: S3Object
---

# Ceph S3 Bucket Monitor

## Purpose

Use this engine to monitor the contents of an S3 bucket for new files. The bucket must be hosted on a Ceph cluster, as this engine relies extensively on its <a href="https://docs.ceph.com/en/nautilus/radosgw/notifications/">API</a> for configuring and handling the bucket events.

Ceph supports HTTP, AMQP 0.9.1 and Kafka push-endpoints to send the events to. Currently this engine only supports AMQP 0.9.1, implemented by for example RabbitMQ and Apache Qpid.

This engine marks all files as <i>Saved</i> when passing them to the Queue manager.

## Options

* <b>Ceph Endpoint</b>: the URL of the Ceph endpoint to connect to. This must start with <i>https://</i>
* <b>Bucket Name</b>: the name of the bucket that will be monitored for changes.
* <b>Access Key</b>: the access key belonging to the RadosGW user that will be used by the engine.
* <b>Secret Key</b>: the secret key that is associated with the access key.

The following options are availabled when clicking the Advanced Settings button:

* <b>Process existing files in bucket</b>: turn this option on to add existing objects to the queue manager before starting the bucket monitor.
* <b>Allowed filename patterns</b>: enter a file extension e.g. *.txt, *.csv (always include the asterisk) to only process files of
that type, any other file written to the directory will be ignored.
* <b>Ignored filename patterns</b>: enter a file extension e.g. *.txt, *.csv (always include the asterisk) to exclude files of
these types, any other file written to the directory will be processed.

Use the radiobuttons to select the appropriate push-endpoint and provide appropriate values for the required parameters.

#### AMQP 0.9.1

* <b>Hostname</b>: the hostname of the AMQP 0.9.1 broker.
* <b>Username</b>: the username to use when establishing a connection with the broker.
* <b>Password</b>: the password to use when establishing a connection with the broker.
* <b>Producer Port</b>: the port on the broker instance that will be used to connect to from Ceph (the producer).
* <b>Consumer Port</b>: the port on the broker instance that will be used to connect to from this machine (the consumer).
* <b>Consumer Use SSL</b>: if enabled, the connection to the broker from the local machine will be SSL encrypted. Usually port 5671 is used when SSL is enabled.
* <b>CA certificate</b>: if the broker SSL certificates have been self-signed, set this value to a file containing the PEM certificate of the Certificate Authority.
* <b>Exchange</b>: the exchange to be used on the broker. Note that Ceph currently requires all its connections to the same push-endpoint to use the same exchange!
* <b>Vhost</b>: the vhost to use on the broker.

## Exported File Format

<b>S3Object</b>

## Author

Tom Schoonjans