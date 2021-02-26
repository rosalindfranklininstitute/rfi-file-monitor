---
layout: default
title: Home

---


## Welcome to the official **RFI-File-Monitor** manual!

The _RFI-File-Monitor_ is a desktop app for monitoring directories, S3 buckets etc. for changes: whenever a new file has been created or an existing one has been changed, a pipeline of [operations](operations/) will be kicked off. [Engines](engines/) do the monitoring, and generate the stream of files that is sent to the [queue manager](usage/).

We ship several engines and operations by default, and it should be rather easy to write new ones yourself!
