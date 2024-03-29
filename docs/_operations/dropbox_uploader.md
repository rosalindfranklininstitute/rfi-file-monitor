---
layout: default
title: Dropbox Uploader
supported: [RegularFile, Directory]
---

# Dropbox Uploader

## Purpose

This operation allows for uploading files that were registered by the active engine to a Dropbox account. We registered the RFI-File-Monitor as a Dropbox app with scope limited to a dedicated folder within an account, meaning that the Monitor does not have access to your other Dropbox files.
To use this operation, you will need a (free) <a href="https://www.dropbox.com/basic">Dropbox account</a>. 

## Options

* <b>Destination folder</b>: the name of the directory that will be created (if required) in the RFI-File-Monitor apps folder of your Dropbox account to upload files from this session into.
* <b>Email address</b>: the email address that is tied to the Dropbox account that you want to upload to.

When the email address has been introduced, click the <i>Validate</i> button to configure the RFI-File-Monitor Dropbox app in your settings if you're a first time user. Otherwise, the refresh token will be fetched from the system keyring, which may require you to type in your password to unlock the keyring.

If you want to stop using the Dropbox uploader, we recommend to disconnect the RFI-File-Monitor Dropbox app in your Dropbox Settings.

It is possible to add multiple Dropbox accounts to a pipeline, as long as they have different email addresses.

## Supported File Formats

<b>RegularFile</b>, <b>Directory</b>

## Author

Tom Schoonjans