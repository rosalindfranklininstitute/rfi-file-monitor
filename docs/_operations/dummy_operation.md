---
layout: default
title: Dummy operation
supported: [RegularFile, S3Object, URL, Directory]
---

# Dummy operation

## Purpose

This operation does nothing useful and is used for testing purposes only.
Every run takes 10 seconds.

## Options

Potentially interesting options are:

* <b>Skip randomly</b>: with this option checked, a small fraction of the runs will raise a SkippedOperation exception, indicating that the operation has been run successfully already.
* <b>Fail randomly</b>: with this option checked, a small fraction of runs will end in failure.

## Supported File Formats

<b>RegularFile</b>, <b>S3Object</b>, <b>URL</b>, <b>Directory</b>

## Author

Tom Schoonjans