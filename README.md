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


