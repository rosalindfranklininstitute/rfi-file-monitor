from setuptools import setup

setup(
    name="rfi-file-monitor",
    version="0.1.0",
    description="Easy to use file monitor GUI with user-definable operations",
    author="Tom Schoonjans",
    author_email="Tom.Schoonjans@rfi.ac.uk",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: BSD License",
        "Natural Language :: English",
        "Operating System :: POSIX :: Linux",
        "Operating System :: Microsoft",
        "Operating System :: MacOS :: MacOS X",
        "Programming Language :: Python :: 3.8",
    ],
    python_requires='>=3.8',
    packages=[
        "rfi_file_monitor",
        "rfi_file_monitor.data"
    ],
    package_data={
        'rfi_file_monitor.data': [
            '*.ui',
            '*.png',
        ],
    },
    install_requires=["setuptools", "PyGObject", "boto3"],
    entry_points={
        "rfi_file_monitor.operations": [
            "DummyOperation = rfi_file_monitor.operations.dummy_operation:DummyOperation",
        ],
        'console_scripts': [
            'rfi-file-monitor=rfi_file_monitor:main',
        ],
    },
    license="BSD license",
    #test_suite="tests",
    url="https://github.com/rosalindfranklininstitute/rfi-file-monitor",
)