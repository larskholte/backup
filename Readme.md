backup.py
=========

backup.py is a very flexible script for merging and copying files and directories. It is intended to be used for backup purposes, so hardlinks are used to copy files between directories on the same filesystem.

Examples
--------
Basic usage would be to merge your home directory with a previous backup, creating a new backup.
```
$ backup.py merge /home/larskholte /mnt/backup/2016-01-27_08-27 /mnt/backup/2016-01-28_16-25
```
Of course, you would want to automate this process so it runs every day without you having to type it out. That, as they say, is an exercise left to the reader. ;)
