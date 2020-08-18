# RFI-File-Monitor

[![PyPI version](https://badge.fury.io/py/rfi-file-monitor.svg)](https://badge.fury.io/py/rfi-file-monitor) ![CI](https://github.com/rosalindfranklininstitute/rfi-file-monitor/workflows/CI/badge.svg?branch=master&event=push) [![Total alerts](https://img.shields.io/lgtm/alerts/g/rosalindfranklininstitute/rfi-file-monitor.svg?logo=lgtm&logoWidth=18)](https://lgtm.com/projects/g/rosalindfranklininstitute/rfi-file-monitor/alerts/) [![Language grade: Python](https://img.shields.io/lgtm/grade/python/g/rosalindfranklininstitute/rfi-file-monitor.svg?logo=lgtm&logoWidth=18)](https://lgtm.com/projects/g/rosalindfranklininstitute/rfi-file-monitor/context:python)

## Installation instructions

Installing this package is easiest when using an [Anaconda](https://www.anaconda.com/products/individual) or [Miniconda](https://docs.conda.io/en/latest/miniconda.html) environment, and works on macOS, Linux and Windows.
Otherwise, this may be quite complicated, given that this package depends on Gtk+3 and its dependencies...

Assuming you have opened a UNIX terminal or Windows PowerShell with access to the conda executable, use the following commands to install `RFI-File-Monitor` in development mode:

1. cd to the directory containing the RFI-File-Monitor source code
2. `conda env create -f environment.yml`
3. `conda activate rfi-file-monitor`
4. `pip install -e .`

After this, you should be able to launch the software simply by executing `rfi-file-monitor`.

Don't forget to execute `conda activate rfi-file-monitor` when you want to launch the software from a new or different terminal/shell.

### Raspberry Pi

To run the RFI-file-monitor on a Raspberry Pi, you will need to install a 64-bit operating system. We are currently running the Raspberry Pi OS 64 bit beta, which seems to work fine. You can download the latest build [here](https://www.raspberrypi.org/forums/viewtopic.php?t=275370).

Afterwards, download and run the aarch64 [miniforge](https://github.com/conda-forge/miniforge) installer:

1. `wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-aarch64.sh`
2. `sh Miniforge3-Linux-aarch64.sh`
3. Go through the questions and when all is done, open a new shell, and follow the steps in the preceding section to get a functional RFI-File-Monitor
