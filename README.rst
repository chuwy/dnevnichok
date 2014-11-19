==========
dnevnichok
==========

Poorman's TUI-based replacement for `Day One App <http://dayoneapp.com/>`_ with Vim keys and reStructuredText support (and without MD ahahaha).
Uses Git as backend and SQLite as cache.

Features
~~~~~~~~

+ Navigating through directories with notes
+ Tagging: add ``:tags:`` field list with tags separated with commas and they'll appear in DB in the next repopulation
+ Notes saved with date of add to repo (``git log -1 --format="%ad" --date=iso --diff-filter=A -- mynote.rst``) and last modification (``git log -1 --format="%ad" --date=iso  -- mynote.rst``)
+ Search by file name with ``/``

Usage
~~~~~

Keybindings
------------

===== ==============
 Key   What it does
===== ==============
``j`` down
``k`` up
``h`` to the parent
``l`` open
``r`` repopulate DB
``t`` show tags
``a`` show all notes
``f`` show dirs
``q`` quit
===== ==============



Requirements
~~~~~~~~~~~~

+ Python 3.4 (I think it should work with versions below, but I didn't tested yet)
+ docutils

That's all. Stay tuned.


ToDo List
~~~~~~~~~

+ MonthManager
+ New note
+ Full-text search (grep)
+ Pull & Push to git
+ Show git status somewhere
+ Sorting: size, date, name
+ Refactor
+ Prettify
