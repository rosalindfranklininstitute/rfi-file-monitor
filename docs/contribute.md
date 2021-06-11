---
layout: default
title: Contributor Guidelines

---

## Contributor Guidelines

So you have been using the RFI-File-Monitor and think that it's really cool but you feel that it lacks an engine or operation, or some other neat feature that would make your life easier, and are willing to write a bit of code to do something about that.

If this is the case, then you have come to the right place as you will find all the necessary information here to get you started.

### Getting started

The RFI-File-Monitor is written entirely in Python code, so you will need to be familiar with that programming language. We initially decided to start writing code using features that were added in what was at the time the most recent release of the Python interpreter (3.8). This means that you can use some new cool additions to the language like the [walrus operator](https://realpython.com/lessons/assignment-expressions/) `:=`. There are currently no plans to increase the minimum required version to more recent releases of Python.

You will know by now that the RFI-File-Monitor is a desktop app, meaning that it contains code to display the different widgets that make up the graphical user interface (GUI). A decision was made early on to use [Gtk](https://www.gtk.org) for this, through [PyGobject](https://pygobject.readthedocs.io/en/latest/). We are currently using the third major release of Gtk ("Gtk3"), but there are plans to [update](https://github.com/rosalindfranklininstitute/rfi-file-monitor/issues/186) this to Gtk4, which was released in December 2020, about six months after we started development of the RFI-File-Monitor.

To learn the basics of developing Gtk3 GUIs with Python, we strongly recommend looking at the excellent [The Python GTK+ 3 Tutorial](https://python-gtk-3-tutorial.readthedocs.io/en/latest/), which comes with lots of useful examples. 

You will almost certainly also need to rely on the [PyGObject API Reference](https://lazka.github.io/pgi-docs/index.html), which contains all of the Gtk3 API as it is used from Python, as well as all of its dependencies such GLib, Pango etc, which you are likely to end up using at some point.

We recommend that you setup a conda development environment, based on the environment.yml file that is included in the repo:

```
conda env create -f environment.yml
conda activate rfi-file-monitor
```

If you plan on writing an engine or operation that you think belongs in our core releases, you should first confirm with us that this is fine, by opening an [issue](https://github.com/rosalindfranklininstitute/rfi-file-monitor/issues) and laying out your plans to us. If we approve, you should fork our repository, create a branch, add your new code and open a pull request for us to review.

However, if we believe that your plans are not appropriate for inclusion into our git repository, you should create a new Python project altogether and register your operations and/or engines using entrypoints in your package config file.

### The classes

A list of the main classes that make up the codebase, what they are used for, and how they rely on each other.

### Writing your own Operation

An overview of the different methods that can and should be implemented by any Operation.

### Writing your own Engine

An overview of the different methods that can and should be implemented by any Engine.

### Adding new Preferences

### How do I use my new Operation, Engine or Preference?

The RFI-File-Monitor will look around your Python installation for all compatible operations, engines and preferences, and populate the GUI with them afterwards. 

Python packages can announce their operations and engines through entrypoints, which are defined in the config file of your project (setup.cfg, pyproject.toml,...).

Have a look at our [setup.cfg](https://github.com/rosalindfranklininstitute/rfi-file-monitor/blob/b73dd80327dbc72e96fc0d71ef0d3dbf04fde0b6/setup.cfg#L45-L65) file for an example on how to do this.

When modifying your config file, you will need to reinstall the package:

```bash
pip uninstall my-cool-package
pip install -e .
```

Afterwards your operation should get picked up by the RFI-File-Monitor next time you launch it.
