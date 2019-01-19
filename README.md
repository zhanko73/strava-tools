strava-tools
============

Library for web-scraping Strava data.

> This library became as a fork from [loisaidasam/stravalib-scraper](https://github.com/loisaidasam/stravalib-scraper) with some extentions
> - a shell
> - load following activity feed
> - **send batch kudos**
> - display / filter activities

Note: Strava does have a [developer portal](https://developers.strava.com/) complete with a proper API and examples. This web-scraping based library is written to complete the lack of feature of the standard API. Accessing Friends' acitivities and interations with them like kudoing.


Installation via PyPi:
-------------

```
$ pip install strava-tools
```

Command line:
-----------------------

To simply start the strava shell:

```
$ strava-shell
strava >>
```
Here is basic example on how to display, load and send kudos to people as batch

```
strava >> login
Username:
Password:
Loaded 10 activities
strava >> activities
Activities 10/10
Kudo time              athlete           title
----+-----------------+-----------------+------------------------------
✓    Today at 4:41 PM  Cyr*************  Parcour*************
✓    Today at 4:39 PM  Jay*************  Natatio*************
✓    Today at 4:24 PM  Der*************  Finishi*************
✓    Today at 3:41 PM  Ad *************  Afterno*************
✓    Today at 3:33 PM  Geo*************  Course *************
✓    Today at 2:44 PM  Nic*************  Randonn*************
     Today at 1:52 PM  Mad*************  Apprent*************
✓    Today at 1:08 PM  Céd*************  Derny t*************
✓    Today at 12:44 PM Mad*************  Apprent*************
✓    Today at 12:00 PM Nor*************  Belle a*************
strava >> activities -a mad
Activities 2/10
Kudo time              athlete     title
----+-----------------+-----------+-----------------------
     Today at 1:52 PM  Mad*************  Apprent*************
✓    Today at 12:44 PM Mad*************  Course *************
strava >> load 500
Loaded 82 activities
strava >> activities -a mad
Activities 3/92
Kudo time                  athlete     title
----+---------------------+-----------+-----------------------
     Today at 1:52 PM      Mad*************  Apprent*************
✓    Today at 12:44 PM     Mad*************  Course *************
     Yesterday at 12:44 PM Mad*************  Natatio*************
strava >> kudo
Sending kudo to Mad************* for Apprent*************
Ok
Sending kudo to Mad************* for Natatio*************
Ok
strava >> activities -a mad
Activities 3/92
Kudo time                  athlete     title
----+---------------------+-----------+-----------------------
*    Today at 1:52 PM      Mad*************  Apprent*************
✓    Today at 12:44 PM     Mad*************  Course *************
*    Yesterday at 12:44 PM Mad*************  Natatio*************
```
