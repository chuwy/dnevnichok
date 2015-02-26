==========
dnevnichok
==========

Poorman's TUI-based replacement for `Day One App <http://dayoneapp.com/>`_ with Vim keys and reStructuredText support (and without MD ahahaha).
Uses Git as backend and SQLite as cache.

Even if you can afford yourself an iPhone with Day One App and you don't use old IBM PC with VGA monitor without GUI, dnevnichok still can be useful for example if you blogging with `Pelican <http://getpelican.com>`_ or writing documentation (may be even a book!) with `Sphinx <http://sphinx-doc.org/>`_. It helps you to search and structuring your collection of reStructuredText documents.

Features
~~~~~~~~

+ Navigating through directories with notes
+ Tagging: add ``:tags:`` field list with tags separated with commas and they'll appear in DB in the next repopulation
+ Favorites: add empty ``:favorite:`` field list.
+ Notes saved with date of add to repo (``git log -1 --format="%ad" --date=iso --diff-filter=A -- mynote.rst``) and last modification (``git log -1 --format="%ad" --date=iso  -- mynote.rst``)
+ Search by file name with ``/``

Usage
~~~~~

On first launch it will ask you about path to your notes. It must be a git repository with your reStructuredText notes.

General Keys
------------

===== ==============
 Key   What it does 
===== ==============
``j`` down          
``k`` up            
``h`` to the parent 
``l`` open          
``r`` repopulate DB 
``q`` quit          
``N`` new diary note
===== ==============

Managers
--------

===== ==============
 Key   What it does 
===== ==============
``M`` Modified
``F`` Favorites     
``L`` Months        
``f`` Files and dirs
``t`` Tags          
``a`` All           
===== ==============
                        
Requirements
~~~~~~~~~~~~

+ Python>=3.3          
+ docutils             

That's all. Stay tuned.+ Pull & Push to git

ToDo List
~~~~~~~~~
+ Sorting: size, date, name
+ MonthManager [X]
+ New note [X]
+ Full-text search [X]
+ Show git status somewhere [X]
+ Refactor [X]
+ Prettify [X]
