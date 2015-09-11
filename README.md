# zbxora
Zabbix Oracle monitoring plugin

Written in python, tested with python 2.6 and 2.7.
Using cx_Oracle
purpose is monitoring an Oracle database in an efficient way.
Optionally calling zabbix_sender to upload data

Supports Oracle 9,10,11,12 RAC,asm and plugin databases
Tested with Oracle 11,12 RAC,standby,asm and plugin databases

usage zbxora.py -c configfile
resulting in log to stdout and datafile in specified out_dir/{configfile}.zbx

sample config:
- `bin/zbxora.py`
- `bin/zbxora_sender`
- `bin/zbxora_starter`

database config files:
- `etc/zbxora.fsdb02.cfg`

template for database config file: (copy to zbxora.{configname}.cfg)
- `etc/zbxora_config_template.cfg`

default checks files:
- `etc/zbxora_checks.asm.11.cfg`
- `etc/zbxora_checks.primary.11.cfg`
- `etc/zbxora_checks.primary.12.cfg`
- `etc/zbxora_checks.standby.11.cfg`

site checks files - examples:
- `etc/zbxora_checks.ebs.cfg`
- `etc/zbxora_checks.sap.cfg`


example config file: zbxora.fsdb02.cfg
--------------------------------------
```
[zbxora]
db_url: //localhost:15214/fsdb02
username: cistats
password: knowoneknows
role: normal
# for ASM instance role should be SYSDBA
out_dir: $HOME/zbxora_out
hostname: testhost
checks_prefix: etc/zbxora_checks
site_checks: sap,ebs
to_zabbix_method: NOzabbix_sender
# if to_zabbix_method is zabbix_sender, every cycle a sender process is started
to_zabbix_args: zabbix_sender -z 127.0.0.1 -T -i 
# the output filename is added to to_zabbix_args
```

When using this configfile ( zbxoa.py -c etc/zbxora.fsdb02.cfg )
zbxora.py will read the configfile
and try to connect to the database using db_url
If all parameters are correct zbxora will keep looping forever.
Using the site_checks as shown, zbxora tries to find them in {checks_prefix}_sap.cfs
and in {checks_prefix}_ebs.cfg (just specify a comma separated list for this)
Outputfile containing the metrics is created in out_dir/zbxora.fsdb02.zbx

After having connected to the sepcified service, zbxora finds out the instance_type and version,
after which the database_role is determined, if applicable.
Using these parameters the correct zbxora_checks_X.Y.cfg file is chosen.

After having read the checks_files, a lld array containing the queries is written before
monitoring starts. When monitoring starts, first the *discovery* section is executed.
This is to discover the instances, tablespaces, diskgroups, or whatever you want
to monitor.

zbxora also keeps track of the used queries.
zbxora executes queries and expects them to return a valid zabbix_key and values.
The zabbix_key that the queries return should be known in zabbix in your zabbix_host
(or be discovered by a preceding lld query in a *discover* section)

If a database goes down, zbxora will try to reconnect until killed.
When a new connection is tried, zbxora reads the config file, just in case
there was a change.
If a checks file in use is changed, zbxora re-reads the file and logs about this.

zbxora's time is mostly spent sleeping. It wakes-up every minute and checks if a
section has to be executed or not. Every section contains a minutes:X parameter that 
specifies how big the monitor interval should be for that section. The interval is 
specified in minutes. If at a certain moment multiple sections are to be executed,
they are executed all after each other. If for some reason the checks take longer than a
minute, an interval is skipped.

The idea for site_checks is to have application specific checks in them. The regular checks
should be application independent and be generic for that type and version of database.
For RAC databases, just connect using 1 instance
For pluggable database, just connect to a global account to monitor all plugins

zbxora_starter:
this is an aide to [re]start zbxora in an orderly way. Put it in the crontab, every minute.
It will check the etc directory (note the lack of a leading '/') and start the configuration
files named zbxora.{you_config}.cfg, each given their own logfile. Notice the sleep in the start
sequence. This is done to make sure not all concurrently running zbxora sessions awake at
the same moment. Now their awakenings is separated by a second.

zbxora_sender:
This convenient when monitoring lot's of databases from one client. In that case it is more
efficient to collect all output files in zbxora_out/ and upload them in one session to zabbix.
It is possible to have zbxora call zabbix_sender but this is not implemented in the most
efficient way.

TODO: make zbxora.py open a pipe to zabbix_sender and use that all the time instead of opening
a new session every minute.

# Warning:
Use the code at your own risk. It is tested and seems to be functional. Use an account with the
least required privileges, both on OS as on database leven.
Don't use a dba type account for this.

database user creation:
```
create user cistats identified by knowoneknows;
grant create session, select any dictionary, oem_monitor to cistats;
```

In Oracle 12 - when using pluggable database:
```
create user c##cistats identified by knowoneknows;
alter user c##cistats set container_data all = container = current;
grant create session, select any dictionary, oem_monitor, dv_monitor to c##cistats;
```

# extra warning:
I have written this in python but not in a pythonic style.
A little cleanup to convert this to clean python code - and preserving efficiency - is welcome.
