---
layout: default
title: Files Monitor
exported: RegularFile
---

# Files Monitor

## Purpose

The Files Monitor is the default (and oldest) engine of the RFI-File-Monitor. Based on <a href="https://pypi.org/project/watchdog/">Watchdog</a>, it will monitor a given directory for new files, as well as changes to these files, and report them to the Queue Manager.

## Options

* <b>Monitored Directory</b>: the directory that will be monitored by the engine.

The following options are availabled when clicking the Advanced Settings button:

* <b>Monitor target directory recursively</b>: this setting determines whether files and directories, created in subfolders of the monitored directory should also be monitored for changes.
* <b>Process existing files in target directory</b>: turn this option on to add existing files (with status <i>Saved</i>) to the queue manager before launching Watchdog.
* <b>Allowed filename patterns</b>: enter a file extension e.g. *.txt, *.csv (always include the asterisk) to only process files of
that type, any other file written to the directory will be ignored.
* <b>Ignored filename patterns</b>: enter a file extension e.g. *.txt, *.csv (always include the asterisk) to exclude files of
these types, any other file written to the directory will be processed.

## Exported File Format

<b>RegularFile</b>

## Author

Tom Schoonjans