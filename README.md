# Plesk-MWES Connector

Plesk-MWES Connector is a connector for bridging Plesk and MailWasher Enterprise Server. This script is intended for Plesk-based server administrators. If you are a desktop user or are administrating a single-site setup you are in the wrong place; please see http://www.firetrust.com for a better suited solution.

__Please note:__ MailWasher Enterprise Server will be referred to as MWES from this point forward. Plesk Panel will simply be referred to as Plesk.

## Features

* Domain names will be created and removed within MWES when created or removed in Plesk. This includes aliases and subdomains!
* Full E-mail reporting and receipts for all Plesk-MWES Connector actions.
* Automatic synchronization of domain names via cron, or a scheduled task. This function ensures all domain names within Plesk are in MWES, and that all domain names not in Plesk are removed from MWES.
* Manual synchronization via the command line.
* Manage MWES domains via the command line.

## Requirements

Linux 
Plesk 8.6+.  
MailWasher Enterprise Server (MWES) 2.8.1.0+.  
Python 2.6+ (Untested with prior versions).  
Python Modules: pycurl, smtplib, urllib (Most should be standard on Linux distributions).

__Note for Windows Server users:__ This script will work just fine, but I do not provide installation instructions. A lot of mucking about with Python libraries is required but it is easy enough to figure out!

## Important Information

### Synchronization

All domain names that are NOT in Plesk will be REMOVED from MWES. If you want to use domains in MWES that are not in Plesk you will need to avoid this function entirely.

The primary purpose of synchronization is to be run daily via a scheduler to ensure that data between Plesk and MWES is consistant. If a domain is added to Plesk but is not in MWES then all mail going to that domain will be immediately rejected! Running the _sync_ command daily ensures that at the longest a domain's E-mail will be out of action for 24 hours in a worse case scenario. While desychronization should never naturally occur it is HIGHLY RECOMMENDED a daily sync is performed.

## Installation

The following steps assume you have Plesk and MWES installed and running with a working configuration. If you have not yet gotten to this point, please refer to the MWES documentation for installation instructions.

I have a detailed post about installing MWES in a Plesk environment on my blog:  
http://a.llen.co.nz/chris/2011/09/installing-mailwasher-enterprise-server-in-a-plesk-panel-environment/

### Plesk-MWES-Connector

1. Copy _plesk-mwes-connector.py_ to _/usr/local/bin_.
2. Set the owner of the script to _root_, and change the permissions to _u:rwx,g:---,o:---_
3. It is now safe to configure the script. Fire up your favorite editor and supply the information required in the EDIT section of the script.
4. You should now import ALL domain names into MWES via the sync tool. If you installed the script in the default location:  
`/usr/local/bin/plesk-mwes-connector.py sync`  
If your configuration is wrong you will find out at this point. Correct the error and repeat this step. If you have notifications enabled you will receive a synchronization report.
5. Please follow the appropriate steps below for your version of Plesk. The instructions will assume the script is installed in the default location.

### Plesk 8.6 to 9.3

1. Login to Plesk as _admin_ and browse to the _Event Management_ tool.
2. Add the _Events_ below with the following settings: _user_: _root_ and _priority_: _normal (50)._  
  * __Domain alias created__  
    `/usr/local/bin/plesk-mwes-connector.py add-domain <new_domain_alias_name>`
  * __Domain alias deleted__  
    `/usr/local/bin/plesk-mwes-connector.py remove-domain <old_domain_alias_name>`
  * __Domain alias updated__  
    `/usr/local/bin/plesk-mwes-connector.py rename-domain <old_domain_alias_name> <new_domain_alias_name>`
  * __Subdomain created__  
    `/usr/local/bin/plesk-mwes-connector.py add-domain <new_subdomain_name>.<new_domain_name>`
  * __Subdomain deleted__  
    `/usr/local/bin/plesk-mwes-connector.py remove-domain <old_subdomain_name>.<old_domain_name>`
  * __Subdomain updated__  
    `/usr/local/bin/plesk-mwes-connector.py rename-domain <old_subdomain_name>.<old_domain_name> <new_subdomain_name>.<new_domain_name>`
  * __Website created__  
    `/usr/local/bin/plesk-mwes-connector.py add-domain <new_domain_name>`
  * __Website deleted__  
    `/usr/local/bin/plesk-mwes-connector.py remove-domain <old_domain_name>`  
  * __Website updated__  
    `/usr/local/bin/plesk-mwes-connector.py rename-domain <old_domain_name> <new_domain_name>`

### Plesk 9.5 - 10.x and above

1. Login to Plesk as _admin_ and browse to the _Server Management > Tools & Utilities > Event Management_ section.
2. Add the _Events_ below with the following settings: _user_: _root_ and _priority_: _normal (50)._
  * __Domain alias created__  
    `/usr/local/bin/plesk-mwes-connector.py add-domain ${NEW_DOMAIN_ALIAS_NAME}`
  * __Domain alias deleted__  
    `/usr/local/bin/plesk-mwes-connector.py remove-domain ${OLD_DOMAIN_ALIAS_NAME}`
  * __Domain alias updated__  
    `/usr/local/bin/plesk-mwes-connector.py rename-domain ${OLD_DOMAIN_ALIAS_NAME} ${NEW_DOMAIN_ALIAS_NAME}`
  * __Subdomain created__  
    `/usr/local/bin/plesk-mwes-connector.py add-domain ${NEW_SUBDOMAIN_NAME}.${NEW_DOMAIN_NAME}`
  * __Subdomain deleted__  
    `/usr/local/bin/plesk-mwes-connector.py remove-domain ${OLD_SUBDOMAIN_NAME}.${OLD_DOMAIN_NAME}`
  * __Subdomain updated__  
    `/usr/local/bin/plesk-mwes-connector.py rename-domain ${OLD_SUBDOMAIN_NAME}.${OLD_DOMAIN_NAME} ${NEW_SUBDOMAIN_NAME}.${NEW_DOMAIN_NAME}`
  * __Website created__  
    `/usr/local/bin/plesk-mwes-connector.py add-domain ${NEW_DOMAIN_NAME}`
  * __Website deleted__  
    `/usr/local/bin/plesk-mwes-connector.py remove-domain ${OLD_DOMAIN_NAME}`  
  * __Website updated__  
    `/usr/local/bin/plesk-mwes-connector.py rename-domain ${OLD_DOMAIN_NAME} ${NEW_DOMAIN_NAME}`


## Command-line Options

The following command line options are available:

* Add a domain:  
`plesk-mwes-connector.py add-domain <domain name>`  
* Rename a domain:  
`plesk-mwes-connector.py rename-domain <old domain name> <new domain name>`  
* Remove a domain:  
`plesk-mwes-connector.py remove-domain <domain name>`  
* Synchronize all domains in MWES with Plesk, or just import all domains from Plesk in to MWES for the first time:  
`plesk-mwes-connector.py sync`

## Support and Contact Info.

This script was written by Chris Allen of Allenmara Computers, Ltd.

If you would like support, please contact me directly via chris@allenmara.co.nz

## License

This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or
distribute this software, either in source code form or as a compiled
binary, for any purpose, commercial or non-commercial, and by any
means.

In jurisdictions that recognize copyright laws, the author or authors
of this software dedicate any and all copyright interest in the
software to the public domain. We make this dedication for the benefit
of the public at large and to the detriment of our heirs and
successors. We intend this dedication to be an overt act of
relinquishment in perpetuity of all present and future rights to this
software under copyright law.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

For more information, please refer to <http://unlicense.org/>

