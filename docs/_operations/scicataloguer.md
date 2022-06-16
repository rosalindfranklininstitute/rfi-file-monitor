---
layout: default
title: SciCataloguer
supported: [RegularFile, Directory]
---

# SciCataloguer

## Purpose

This operation creates metadata entries for data taken on the instrument and uploads them into the catalogue. 
It automatically captures the required data from the previous operations. It can be used for both raw and derived datasets. 
Uses pyscicat module to establish connection to SciCat. SciCat documentation can be found <a href="https://scicatproject.github.io/documentation/">here</a>.

## Options

* <b>Hostname</b>: the fully qualified domain name or IP address of the SciCat server
* <b>Upload location</b>: location for data to be uploaded, designated by upload operation
* <b>Username</b>: the username that will be used to establish the connection with SciCat
* <b>Password</b>: the password that corresponds to the username
* <b>Owner</b>: owner of the dataset
* <b>Owner Group</b>
* <b>Email</b>: contact email for the owner of the dataset
* <b>Orcid</b>: orcid of the owner of the dataset
* <b>Principal Invesigator</b>
* <b>Experiment name</b>: name of the experiment 
* <b>Instrument</b>: instrument used
* <b>Technique</b>: the techique used by the instrument
* <b>Input Datasets</b>: for derived datasets only, comma-separated list of SciCat locations for raw datasets used
* <b>Used Software</b>: for derived datasets only, comma-separated list of software used to derive analysis results

## Prerequisites

The Scicataloguer should be added at the end of any experimental session and should be preceeded by an uploader operation such as S3 Uploader, SFTP Uploader or Dropbox Uploader. 

## Supported File Formats

<b>RegularFile</b>,<b>Directory</b>

## Author
Abigail Alexander