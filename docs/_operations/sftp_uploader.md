---
layout: default
title: SFTP Uploader
supported: [RegularFile, Directory]
---

# SFTP Uploader

## Purpose

Use this operation to upload the monitored files to an SFTP server.

## Options

* <b>Hostname</b>: the fully qualified domain name or IP address of the SFTP server
* <b>Port</b>: the port on which the SFTP server is listening. Default is 22.
* <b>Username</b>: the username that will be used to establish the connection with the SFTP server
* <b>Password</b>: the password that corresponds to the username
* <b>Destination folder</b>: the destination folder on the SFTP server to write the monitored files to. Do not use tildes (~)!! If a relative path is used, it will be assumed to be relative to the home folder of the user that logs in.
* <b>Create destination folder if necessary</b>: if checked, then the destination will be created if necessary.
* <b>Automatically accept new host keys (dangerous!!)</b>: with this option checked, when connecting to an SFTP server for the first time, the host keys will be accepted for the duration of the session. This is potentially dangerous. We recommend using an SSH client to make an initial connection, which will ask explicitly if this host key should be accepted, which will then be picked up by the RFI-File-Monitor.

Advanced Options:

* <b>Override file UNIX permissions</b>: when enabled, the file's permissions will be set to the values specified by manipulating the checkboxes, after the file has been uploaded to the destination server.
* <b>Override directory UNIX permissions</b>: when enabled, any directories created will be set to the selected permissions. Be careful with this option: if the directories are not writeable, you won't be able to upload any files into it.

## Supported File Formats

<b>RegularFile</b>, <b>Directory</b>

## Author

Tom Schoonjans