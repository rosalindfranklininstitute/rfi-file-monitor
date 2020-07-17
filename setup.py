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
            '*.yaml'
        ],
    },
    install_requires=[
        "PyGObject",
        "boto3",
        "munch",
        "watchdog",
        "PyYAML",
        "paramiko"
    ],
    entry_points={
        "rfi_file_monitor.operations": [
            "DummyOperation = rfi_file_monitor.operations.dummy_operation:DummyOperation",
            "S3Uploader = rfi_file_monitor.operations.s3_uploader:S3UploaderOperation",
            "SftpUploader = rfi_file_monitor.operations.sftp_uploader:SftpUploaderOperation",
        ],
        "rfi_file_monitor.preferences": [
            "TestBooleanPreference1 = rfi_file_monitor.preferences:TestBooleanPreference1",
            "TestBooleanPreference2 = rfi_file_monitor.preferences:TestBooleanPreference2",
            "TestBooleanPreference3 = rfi_file_monitor.preferences:TestBooleanPreference3",
            "TestListPreference1 = rfi_file_monitor.preferences:TestListPreference1",
            "TestListPreference2 = rfi_file_monitor.preferences:TestListPreference2",
            "TestDictPreference1 = rfi_file_monitor.preferences:TestDictPreference1",
            "TestDictPreference2 = rfi_file_monitor.preferences:TestDictPreference2",
            "TestDictPreference3 = rfi_file_monitor.preferences:TestDictPreference3",
            "TestStringPreference1 = rfi_file_monitor.preferences:TestStringPreference1",
            "TestStringPreference2 = rfi_file_monitor.preferences:TestStringPreference2",
        ],
        'console_scripts': [
            'rfi-file-monitor=rfi_file_monitor:main',
        ],
    },
    license="BSD license",
    #test_suite="tests",
    url="https://github.com/rosalindfranklininstitute/rfi-file-monitor",
)