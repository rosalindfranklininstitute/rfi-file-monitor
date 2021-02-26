---
layout: default
title: Installation Instructions

---

## Installation instructions

Installing this package is easiest when using an [Anaconda](https://www.anaconda.com/products/individual) or [Miniconda](https://docs.conda.io/en/latest/miniconda.html) environment, and works well on macOS, Linux and Windows.
Otherwise, this may be quite complicated, given that this package depends on Gtk+3 and its rather impressive dependency stack...

### Anaconda (strongly recommended)

The latest stable release is available from conda-forge. We strongly recommend creating a dedicated environment before proceeding:

1. `conda create -n rfi-file-monitor -c conda-forge rfi-file-monitor`
2. `conda activate rfi-file-monitor`
3. `rfi-file-monitor`

### PyPI (discouraged)

It is possible to install _RFI-File-Monitor_ using pip on a Linux or macOS system with python 3.8 or newer, and the complete Gtk+3 stack installed, including gobject-introspection along with its headers (devel package).

When this is done, create a new virtual environment:

1. `python3 -m venv /path/to/new/virtual/environment`
2. `source python3 /path/to/new/virtual/environment/bin/activate`
3. `pip3 install rfi-file-monitor`
4. `rfi-file-monitor`
