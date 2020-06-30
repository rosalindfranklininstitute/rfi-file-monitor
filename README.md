# RFI-File-Monitor

![CI](https://github.com/rosalindfranklininstitute/rfi-file-monitor/workflows/CI/badge.svg?branch=master&event=push) [![Total alerts](https://img.shields.io/lgtm/alerts/g/rosalindfranklininstitute/rfi-file-monitor.svg?logo=lgtm&logoWidth=18)](https://lgtm.com/projects/g/rosalindfranklininstitute/rfi-file-monitor/alerts/) [![Language grade: Python](https://img.shields.io/lgtm/grade/python/g/rosalindfranklininstitute/rfi-file-monitor.svg?logo=lgtm&logoWidth=18)](https://lgtm.com/projects/g/rosalindfranklininstitute/rfi-file-monitor/context:python)

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


