---
layout: default
title: Directories Monitor
exported: Directory
---

# Directories Monitor

## Purpose

The Directories Monitor observes a folder for new subdirectories being created directly within it. This engine exports <i>Directory</i> instances, which are a representation of all files and folders contained within a subdirectory, and operations will be expected to process the entire directory structure contained within.

## Options

* <b>Monitored Directory</b>: the directory that will be monitored by the engine.

The following options are availabled when clicking the Advanced Settings button:

* <b>Process existing directories in target directory</b>: turn this option on to add existing directories (with status <i>Saved</i>) to the queue manager before launching Watchdog.
* <b>Allowed filename patterns</b>: enter a comma separated list of patterns containing wildcards to only consider files matching them.
* <b>Ignored filename patterns</b>: enter a comma separated list of patterns containing wildcards to exclude files that do not match them.
* <b>Allowed directory patterns</b>: enter a comma separated list of patterns containing wildcards to only consider those directories matching them.
* <b>Ignored directory patterns</b>: enter a comma separated list of patterns containing wildcards to exclude directories that do not match them.

## Exported File Format

<b>Directory</b>

## Author

Tom Schoonjans