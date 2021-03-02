---
layout: default
title: Home

---

[![PyPI version](https://badge.fury.io/py/rfi-file-monitor.svg)](https://badge.fury.io/py/rfi-file-monitor) ![CI](https://github.com/rosalindfranklininstitute/rfi-file-monitor/workflows/CI/badge.svg?branch=master&event=push) [![Total alerts](https://img.shields.io/lgtm/alerts/g/rosalindfranklininstitute/rfi-file-monitor.svg?logo=lgtm&logoWidth=18)](https://lgtm.com/projects/g/rosalindfranklininstitute/rfi-file-monitor/alerts/) [![Language grade: Python](https://img.shields.io/lgtm/grade/python/g/rosalindfranklininstitute/rfi-file-monitor.svg?logo=lgtm&logoWidth=18)](https://lgtm.com/projects/g/rosalindfranklininstitute/rfi-file-monitor/context:python)

## Welcome to the official **RFI-File-Monitor** manual!

The _RFI-File-Monitor_ is a desktop app for monitoring directories, S3 buckets etc. for changes: whenever a new file has been created or an existing one has been changed, a pipeline of [operations](operations/) will be kicked off. [Engines](engines/) do the monitoring, and generate the stream of files that is sent to the [queue manager](usage/).

We ship several engines and operations by default, and it should be rather easy to write new ones yourself!
