---
layout: default
title: Usage
filetypes:
    - RegularFile
    - Directory
    - URL
    - S3Object
---

## Launching the RFI-File-Monitor

### Windows

When [installing](install) the _Monitor_ using the Anaconda package manager, you should see an entry for it in the _Start_ menu. Click it to launch the program.

### Linux and macOS

Assuming you installed the _Monitor_ using Anaconda, you will now need to activate the conda environment:

```bash
conda activate rfi-file-monitor
rfi-file-monitor
```

Do not attempt to bypass activating the environment by using the absolute path to the `rfi-file-monitor` executable: this will result in GLib related run-time errors!

## Understanding the RFI-File-Monitor

Before going into a step-by-step guide on how to use this software package, it is probably best to share some of the concepts and terms it is built around to avoid any misunderstandings later on.

The _engine_ is the main driver of activity: it monitors a _provider_ for two kinds of changes:

1. Newly created files
2. Modified files

The _provider_ can be a directory on the local filesystem, an S3 bucket, a file, ..., depending on which [type of _engine_](../engines/) was selected for the session. 
Whenever a new file has been detected by the engine, a corresponding `File` object will be instantiated with status set to `Created`. This object is then added to the [_queue manager_](../misc/queue_manager) that is associated with the session. 

`File`s with `Created` status are effectively ignored by the _queue manager_ until the _engine_ detects that they have been saved or modified: at this point will the _queue manager_ be instructed to change `File` status to `Saved`, which is when things become interesting! After a configurable of time, and assuming no further modifications were detected for this file, will the `File` be queued for processing, corresponding to a change of status to `Queued`.

At this point will the _queue manager_ check if the necessary resources to start the processing pipeline for the `File` are available: one thread is used per pipeline, with the total number of usable threads configurable in the _queue manager_ settings. If the outcome of the check is positive, the pipeline will be started and the `File` status will be set to `Running`.

Processing pipelines consist of a [list of _operations_](../operations), that is defined by the user. Each _operation_ works directly on the `File` itself, not on any new files that may have been produced by a preceding _operation_! It is possible though, to pass information (metadata) down a `File`'s pipeline to influence the behavior of subsequent _operations_. In fact, one can make an _operation_ explicitly depend on another one, producing a run-time error when this condition is not met.

The `File` status will be set to `Success` or `Failure` at the end of the pipeline, depending on its outcome. It should be noted that these statuses do not necessarily represent the final state for the `File` object. Indeed, it is quite possible that the _engine_ detects more modifications of the observed file, leading to its status being reset to `Saved`, which will eventually lead to the `File` being requeued for processing... 

This section can be visualized using the following flowchart:

![RFI-File-Monitor flowchart]({{ '/assets/images/rfi-file-monitor-flowchart.png' | relative_url }})

## File types

The `File` objects that were first used in the previous section are in fact instances of a base class with the same name. Several implementations of this base class exist in this software package, and it should not be hard to write your own. Important here is that the objects that are created by a particular _engine_, are always instances of the same class, derived from `File`, the _exported filetype_. _Operations_ however, can be written to support as many filetypes as necessary. 

The following table summarizes the currently available file types, as well as the _engines_ and _operations_ that support them:

| Filetype | Supporting Engines | Supporting Operations |
| ---------|-------------------|----------------------|
{% for _filetype in page.filetypes -%}
  {%- assign _engines = site.engines | where: "exported", _filetype -%}
  | {{ _filetype }} |
  {%- for _engine in _engines -%}
    [{{ _engine.title }}]({{ _engine.url | relative_url }})
    {%- if forloop.last == false -%}
      ,&nbsp;
    {%- endif -%}
  {%- endfor -%}
  |
  {%- assign _operations = site.operations | where_exp: "_operation", "_operation.supported contains _filetype" -%}
  {%- for _operation in _operations -%}
    [{{ _operation.title }}]({{ _operation.url | relative_url }})
    {%- if forloop.last == false -%}
      ,&nbsp;
    {%- endif -%}
  {%- endfor -%}
  |
{% endfor -%}
