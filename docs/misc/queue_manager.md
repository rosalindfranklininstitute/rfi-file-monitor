---
layout: default
title: Queue Manager

---

# Queue Manager

## Purpose

The Queue Manager keeps a list of all <i>files</i> around that have been detected by the currently active engine.
Initially, when a new file has been added to this list, it will be marked as <i>Created</i>.
Most engine types will after some time detect that the file has been saved, which means that the file is ready for processing.
The engine will then ask the queue manager to update that file's status to <i>Saved</i>.
After some time, assuming there have been no more save events, the file will be upgraded to <i>Queued</i>, meaning that it can now be sent through the operations pipeline for processing.
Only when there's a thread available to do the actual processing, will a <i>Job</i> be created and the file status be changed to <i>Running</i>.
Afterwards, the file status will be changed to <i>Success</i> or <i>Failure</i>, depending on the outcome of the pipeline.

If the engine detects another Save event for a file when it has status <i>Queued</i>, then it will simply be demoted to <i>Saved</i>, delaying the processing for that file.
However, if the the file is already in status <i>Running</i>, <i>Success</i> or <i>Failure</i> when the Save event is recorded, then the file will be requeued for processing.

## Options

The behavior of the Queue Manager may be adjusted by clicking the eponymously named button, which will bring up a dialog with the following options:

* <b>Promote files from 'Created' to 'Saved'</b>: some engines either do not support promoting for <i>Created</i> to <i>Saved</i>, or cannot always be relied on to pick up these Saved events reliably. When this happens, files will be stuck in the queue forever with status <i>Created</i>. This can be avoided by using this option, which will enable automatic promotion to <i>Saved</i> after a selectable number of seconds.
* <b>Delay promoting files from 'Saved' to 'Queued'</b>: sometimes files will be updated multiple files before they can be considered ready for processing. To avoid files being promoted to <i>Queued</i> to soon, it may be useful to increase the minimum amount of time a file has to marked as <i>Saved</i>, before it can be promoted to <i>Queued</i>
* <b>Maximum number of threads to use</b>: this value reflects the number of files may be processed simultaneously. It is limited by the number of CPUs available on the system.
* <b>Remove from table after</b>: when active, successfully processed files will be removed from the table after the requested number of minutes. If the queue manager gets notified of a <i>Saved</i> event for a file that has been removed from the table, it will be added back to it, starting the pipeline all over again.