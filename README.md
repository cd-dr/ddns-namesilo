DNS record updater for namesilo
===============================

Can be used to update multiple DNS records for various hostnames for one domain in your Namesilo account using Namesilo APIs and your API key.

Change the following in `ddns.py`
- Update *NAMESILO_KEY* to your API key (can be found at https://www.namesilo.com/account_api.php).
- Change the *hs* variable inside the *main* function to reflect your list of hostnames. Also the *dom* field to your particular domain of interest.

Call the file with any task scheduler to periodically update your DDNS entries.
