=========================
Python-OpenEVSE changelog
=========================

Some versions are "unreleased" : published in the Git repository but not
released on the *Pyton Package Index*. That's why some versions are not
named here.

v0.3 (2015-08-01)
-----------------

* Possibility to get status changes (they were ignored in previous versions)
* Possibility to get status changes synchronously (threaded read loop)
* Bugfix: retry echo initialization if failed because of chars sent previously

v0.2 (2015-07-30)
-----------------

* Object-oriented code
* Changes related to exceptions and their names
* Bugfix: `fault_counters` returns ints

v0.1a3 (2015-07-15)
-------------------

* Small changes in internal code

v0.1a2 (2015-07-07)
-------------------

* Bugfix: missing `open()`

v0.1a1 (2015-07-03)
-------------------

* First release
