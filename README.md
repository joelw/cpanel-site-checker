cPanel Site Checker
===================

This is a handy tool for administrators keeping an eye on managed and semi-managed cPanel hosting servers. It 
currently does the following:

* Enumerates all accounts and domains on a list of cPanel servers
* Skips any domains that don't resolve in DNS to the that particular server
* Retrieves the text content of the web site and logs it into a file
* Saves a screenshot of the site
* Compare the contents of each web site with its previous snapshot

It will eventually be extended to:

* If a significant difference is encountered, generate an email that contains an alert, as well as
  the before and after screenshots

Strategies for evaluating differences might include:

* Comparison of first 1KB only
* Percentage difference of entire page
* Scanning for warning/error messages, e.g. PHP notices

In order to make operation of the tool as automatic as possible, I'd prefer not to have to configure the
strategy on a per-domain basis - hopefully I'll come up with something that is generic enough to apply
to all of the sites I look after.

It's intended to be run periodically from cron, but you may also wish to invoke it after server-wide
PHP or Apache upgrades, WordPress core and plugin upgrades, account moves between servers, and so on.

Installation
============

* Create an API Token in WHM - not entirely sure which permissions are needed yet
* Copy servers.yml.sample to servers.yml file and fill in the blanks

Database Logging
================

The application logs all check results to a SQLite database in addition to the text file output. 
This enables future web interface functionality for viewing changes over time.

The database file location can be configured in servers.yml:
```yaml
:config:
  :database: site_checker.db  # defaults to site_checker.db if not specified
```

The database contains a `check_results` table with the following columns:
* `timestamp` - ISO 8601 timestamp of the check
* `host` - WHM server hostname
* `user` - cPanel username
* `domain` - Domain name
* `code` - HTTP status code or error message
* `location` - Final URL after redirects
* `digest` - SHA256 hash of page content
* `txt_status` - Text comparison status (different/deleted_duplicate)
* `txt_previous_run` - Previous run date serial
* `screenshot_hash_distance` - Perceptual hash distance between screenshots
* `screenshot_status` - Screenshot comparison status (different/deleted_identical)
* `screenshot_previous_run` - Previous run date serial for screenshot

Usage
=====

Run the script:
```bash
uv run site-checker.py
```

Or make it executable and run directly:
```bash
chmod +x site-checker.py
./site-checker.py
```


