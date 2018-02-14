#!/usr/bin/env python
"""
 free clonable from https://github.com/ikzelf/zbxora/
 (@) ronald.rood@ciber.nl follow @ik_zelf on twitter
 follow @zbxora on twitter
 push your added items/checks using git
 options: -c/--cfile configFile
                     configFile contains config for 1 database and
                                a reference to the checks
 NOTE: a section whose name contains 'discover' is considered to be handled
           as a special case for LLD -> json arrays
 NOTE: consider using Oracle Wallet instead of coding credentials in config
 NOTE: run as a regular database client, not a special account like root or oracle
"""
import json
import collections
import datetime
import time
import sys
import os
import configparser
import resource
import gc
import subprocess
import threading
from argparse import ArgumentParser
from timeit import default_timer as timer
import platform
# from pdb import set_trace
import cx_Oracle as db
VERSION = "1.98"

def printf(format, *args):
    """just a simple c-style printf function"""
    sys.stdout.write(format % args)
    sys.stdout.flush()

def output(host, ikey, values):
    """uniform way to generate the output"""
    timestamp = int(time.time())
    OUTF.write(host + " " + ikey + " " + str(timestamp) + " " + str(values)+ "\n")
    OUTF.flush()

ME = os.path.splitext(os.path.basename(__file__))
PARSER = ArgumentParser()
PARSER.add_argument("-c", "--cfile", dest="configfile", default=ME[0]+".cfg",
                    help="Configuration file", metavar="FILE")
ARGS = PARSER.parse_args()

CONFIG = configparser.RawConfigParser()
if not os.path.exists(ARGS.configfile):
    raise ValueError("Configfile " + ARGS.configfile + " does not exist")

INIF = open(ARGS.configfile, 'r')
CONFIG.read_file(INIF)
DB_URL = CONFIG.get(ME[0], "db_url")
DB_TYPE = "oracle"
USERNAME = CONFIG.get(ME[0], "username")
PASSWORD = CONFIG.get(ME[0], "password")
ROLE = CONFIG.get(ME[0], "role")
OUT_DIR = os.path.expandvars(CONFIG.get(ME[0], "out_dir"))
OUT_FILE = os.path.join(OUT_DIR,
                        str(os.path.splitext(os.path.basename(ARGS.configfile))[0]) + ".zbx")
HOSTNAME = CONFIG.get(ME[0], "hostname")
CHECKSFILE_PREFIX = CONFIG.get(ME[0], "checks_dir")
SITE_CHECKS = CONFIG.get(ME[0], "site_checks")
TO_ZABBIX_METHOD = CONFIG.get(ME[0], "to_zabbix_method")
TO_ZABBIX_ARGS = os.path.expandvars(CONFIG.get(ME[0], "to_zabbix_args")) + " " + OUT_FILE
INIF.close()
CHECKFILES = [[__file__, os.stat(__file__).st_mtime]]
CHECKSCHANGED = [0]

CONNECTCOUNTER = 0
CONNECTERROR = 0
QUERYCOUNTER = 0
QUERYERROR = 0
STARTTIME = int(time.time())
printf("%s start python-%s %s-%s pid=%s Connecting for hostname %s...\n", \
    datetime.datetime.fromtimestamp(STARTTIME), \
    platform.python_version(), ME[0], VERSION, os.getpid(), HOSTNAME
      )
if SITE_CHECKS != "NONE":
    printf("%s site_checks: %s\n", \
        datetime.datetime.fromtimestamp(time.time()), SITE_CHECKS)
printf("%s to_zabbix_method: %s %s\n", \
    datetime.datetime.fromtimestamp(time.time()), TO_ZABBIX_METHOD, TO_ZABBIX_ARGS)
printf("%s out_file:%s\n", \
    datetime.datetime.fromtimestamp(time.time()), OUT_FILE)
SLEEPC = 0
SLEEPER = 1
PERROR = 0
while True:
    try:
        Z = CHECKFILES[0]
        CHECKSFILE = Z[0]
        CHECKSCHANGED = Z[1]
        if CHECKSCHANGED != os.stat(CHECKSFILE).st_mtime:
            printf("%s %s changed, restarting ...\n",
                   datetime.datetime.fromtimestamp(time.time()), CHECKSFILE)
            os.execv(__file__, sys.argv)

        # reset list in case of a just new connection that reloads the config
        CHECKFILES = [[__file__, os.stat(__file__).st_mtime]]
        CONFIG = configparser.RawConfigParser()
        INIF = open(ARGS.configfile, 'r')
        CONFIG.read_file(INIF)
        DB_URL = CONFIG.get(ME[0], "db_url")
        USERNAME = CONFIG.get(ME[0], "username")
        PASSWORD = CONFIG.get(ME[0], "password")
        ROLE = CONFIG.get(ME[0], "role")
        OUT_DIR = os.path.expandvars(CONFIG.get(ME[0], "out_dir"))
        OUT_FILE = os.path.join(OUT_DIR,
                                str(os.path.splitext(os.path.basename(ARGS.configfile))[0])
                                + ".zbx")
        HOSTNAME = CONFIG.get(ME[0], "hostname")
        CHECKSFILE_PREFIX = CONFIG.get(ME[0], "checks_dir")
        SITE_CHECKS = CONFIG.get(ME[0], "site_checks")
        TO_ZABBIX_METHOD = CONFIG.get(ME[0], "to_zabbix_method")
        TO_ZABBIX_ARGS = os.path.expandvars(CONFIG.get(ME[0], "to_zabbix_args")) + " " + OUT_FILE
        if os.path.exists(OUT_FILE):
            OUTF = open(OUT_FILE, "a")
        else:
            OUTF = open(OUT_FILE, "w")

        OMODE = 0
        if ROLE.upper() == "SYSASM":
            OMODE = db.SYSASM
        if ROLE.upper() == "SYSDBA":
            OMODE = db.SYSDBA

        X = USERNAME + "/" + PASSWORD + "@" + DB_URL
        START = timer()
        with db.connect(USERNAME + "/" + PASSWORD + "@" + DB_URL, mode=OMODE) as conn:
            CONNECTCOUNTER += 1
            output(HOSTNAME, ME[0]+"[connect,status]", 0)
            CURS = conn.cursor()
            try:
                CURS.execute("""select substr(i.version,0,instr(i.version,'.')-1),
                    s.sid, s.serial#, p.value instance_type, i.instance_name
                    , s.username
                    from v$instance i, v$session s, v$parameter p 
                    where s.sid = (select sid from v$mystat where rownum = 1)
                    and p.name = 'instance_type'""")
                DATA = CURS.fetchone()
                DBVERSION = DATA[0]
                MYSID = DATA[1]
                MYSERIAL = DATA[2]
                ITYPE = DATA[3]
                INAME = DATA[4]
                UNAME = DATA[5]
            except db.DatabaseError as oerr:
                ERROR, = oerr.args
                if ERROR.code == 904:
                    DBVERSION = "pre9"
                else:
                    DBVERSION = "unk"
            if ITYPE == "RDBMS":
                CURS.execute("""select database_role from v$database""")
                DATA = CURS.fetchone()
                DBROL = DATA[0]
            else:
                DBROL = "asm"
            CURS.close()

            printf("%s connected db_url %s type %s db_role %s version %s" +
                   "\n%s user %s %s sid,serial " +
                   "%d,%d instance %s as %s\n",
                   datetime.datetime.fromtimestamp(time.time()), \
                   DB_URL, ITYPE, DBROL, DBVERSION, \
                   datetime.datetime.fromtimestamp(time.time()), \
                   USERNAME, UNAME, MYSID, MYSERIAL, \
                   INAME, \
                   ROLE)
            if DBROL == "asm":
                CHECKSFILE = os.path.join(CHECKSFILE_PREFIX, DB_TYPE, ITYPE.lower()
                                          + "." + DBVERSION+".cfg")
                # could be asm or ASMPROXY
            elif  DBROL == "PHYSICAL STANDBY":
                CHECKSFILE = os.path.join(CHECKSFILE_PREFIX, DB_TYPE, "standby"
                                          + "." + DBVERSION+".cfg")
            else:
                CHECKSFILE = os.path.join(CHECKSFILE_PREFIX, DB_TYPE, DBROL.lower()
                                          + "." + DBVERSION+".cfg")

            try:
                SQLTIMEOUT = float(CONFIG.get(ME[0], "sql_timeout"))
            except configparser.NoOptionError:
                SQLTIMEOUT = 60.0
            printf('%s using sql_timeout %d\n',
                   datetime.datetime.fromtimestamp(time.time()), \
                   SQLTIMEOUT)
            FILES = [CHECKSFILE]
            CHECKFILES.extend([[CHECKSFILE, 0]])
            if SITE_CHECKS != "NONE":
                for addition in SITE_CHECKS.split(","):
                    addfile = os.path.join(CHECKSFILE_PREFIX, DB_TYPE, addition + ".cfg")
                    CHECKFILES.extend([[addfile, 0]])
                    FILES.extend([addfile])
            printf('%s using checks from %s\n',
                   datetime.datetime.fromtimestamp(time.time()), FILES)

            for CHECKSFILE in CHECKFILES:
                if not os.path.exists(CHECKSFILE[0]):
                    raise ValueError("Configfile " + CHECKSFILE[0]+ " does not exist")
            ## all checkfiles exist

            SLEEPC = 0
            SLEEPER = 1
            PERROR = 0
            CONMINS = 0
            OPENTIME = int(time.time())
            while True:
                NOWRUN = int(time.time()) # keep this to compare for when to dump stats
                RUNTIMER = timer() # keep this to compare for when to dump stats
                if os.path.exists(OUT_FILE):
                    OUTF = open(OUT_FILE, "a")
                else:
                    OUTF = open(OUT_FILE, "w")
                # loading checks from the various checkfiles:
                NEEDTOLOAD = "no"
                for i in range(len(CHECKFILES)): # at index 0 is the script itself
                    z = CHECKFILES[i]
                    CHECKSFILE = z[0]
                    CHECKSCHANGED = z[1]
                    # if CHECKSFILE became inaccessible in run -> crash and no output :-(
                    # change the CHECKSCHANGED to catch that.
                    if CHECKSCHANGED != os.stat(CHECKSFILE).st_mtime:
                        if i == 0: # this is the script itself that changed
                            printf("%s %s changed, restarting ...\n",
                                   datetime.datetime.fromtimestamp(time.time()), CHECKSFILE)
                            os.execv(__file__, sys.argv)
                        else:
                            if CHECKSCHANGED == 0:
                                printf("%s checks loading %s\n", \
                                    datetime.datetime.fromtimestamp(time.time()), CHECKSFILE)
                                NEEDTOLOAD = "yes"
                            else:
                                printf("%s checks changed, reloading %s\n", \
                                    datetime.datetime.fromtimestamp(time.time()), CHECKSFILE)
                                NEEDTOLOAD = "yes"

                if NEEDTOLOAD == "yes":
                    output(HOSTNAME, ME[0] + "[version]", VERSION) # try once in a while
                    OBJECTS_LIST = []
                    SECTIONS_LIST = []
                    FILES_LIST = []
                    ALL_CHECKS = []
                    for i in range(len(CHECKFILES)):
                        z = CHECKFILES[i]
                        CHECKSFILE = z[0]
                        E = collections.OrderedDict()
                        E = {"{#CHECKS_FILE}": i}
                        FILES_LIST.append(E)

                    FILES_JSON = '{\"data\":'+json.dumps(FILES_LIST)+'}'
                    output(HOSTNAME, ME[0]+".files.lld", FILES_JSON)
                    CRASH = 0
                    for i in range(1, len(CHECKFILES)):
                        z = CHECKFILES[i]
                        CHECKSFILE = z[0]
                        CHECKS = configparser.RawConfigParser()
                        try:
                            CHECKSF = open(CHECKSFILE, 'r')
                            output(HOSTNAME, ME[0] + "[checks," + str(i) + ",name]", CHECKSFILE)
                            output(HOSTNAME, ME[0] + "[checks," + str(i) + ",lmod]",
                                   str(int(os.stat(CHECKSFILE).st_mtime)))
                            try:
                                CHECKS.read_file(CHECKSF)
                                CHECKSF.close()
                                output(HOSTNAME, ME[0] + "[checks," + str(i) + ",status]", 0)
                            except configparser.Error:
                                output(HOSTNAME, ME[0] + "[checks," + str(i) + ",status]", 13)
                                printf("%s\tfile %s has parsing errors %s %s ->(13)\n",
                                       datetime.datetime.fromtimestamp(time.time()),
                                       CHECKSFILE)
                                # CRASH=13
                                # raise
                        except IOError as io_error:
                            output(HOSTNAME, ME[0] + "[checks," + str(i) + ",status]", 11)
                            printf("%s\tfile %s IOError %s %s ->(11)\n",
                                   datetime.datetime.fromtimestamp(time.time()), CHECKSFILE,
                                   io_error.errno, io_error.strerror)
                            CRASH = 11
                            # raise

                        z[1] = os.stat(CHECKSFILE).st_mtime

                        CHECKFILES[i] = z
                        ALL_CHECKS.append(CHECKS)
                        for section in sorted(CHECKS.sections()):
                            secMins = int(CHECKS.get(section, "minutes"))
                            if secMins == 0:
                                printf("%s\t%s run at connect only\n", \
                                    datetime.datetime.fromtimestamp(time.time()), section)
                            else:
                                printf("%s\t%s run every %d minutes\n", \
                                    datetime.datetime.fromtimestamp(time.time()), section, \
                                    secMins)
                            # dump own discovery items of the queries per section
                            E = collections.OrderedDict()
                            E = {"{#SECTION}": section}
                            SECTIONS_LIST.append(E)
                            x = dict(CHECKS.items(section))
                            for key, sql  in sorted(x.items()):
                                if sql and key != "minutes":
                                    d = collections.OrderedDict()
                                    d = {"{#SECTION}": section, "{#KEY}": key}
                                    OBJECTS_LIST.append(d)
                                    printf("%s\t\t%s: %s\n", \
                                        datetime.datetime.fromtimestamp(time.time()), \
                                        key, sql[0 : 60].replace('\n', ' ').replace('\r', ' '))
                    # checks are loaded now.
                    SECTIONS_JSON = '{\"data\":'+json.dumps(SECTIONS_LIST)+'}'
                    # printf ("DEBUG lld key: %s json: %s\n", ME[0]+".lld", ROWS_JSON)
                    output(HOSTNAME, ME[0]+".section.lld", SECTIONS_JSON)
                    ROWS_JSON = '{\"data\":'+json.dumps(OBJECTS_LIST)+'}'
                    # printf ("DEBUG lld key: %s json: %s\n", ME[0]+".lld", ROWS_JSON)
                    output(HOSTNAME, ME[0] + ".query.lld", ROWS_JSON)
                # checks discovery is also printed
                #
                # assume we are still connected. If not, exception will tell real story
                output(HOSTNAME, ME[0] + "[connect,status]", 0)
                output(HOSTNAME, ME[0] + "[uptime]", int(time.time() - STARTTIME))
                output(HOSTNAME, ME[0] + "[opentime]", int(time.time() - OPENTIME))

                # the connect status is only real if executed a query ....
                for CHECKS in ALL_CHECKS:
                    for section in sorted(CHECKS.sections()):
                        SectionTimer = timer() # keep this to compare for when to dump stats
                        secMins = int(CHECKS.get(section, "minutes"))
                        if ((CONMINS == 0 and secMins == 0) or
                                (secMins > 0 and CONMINS % secMins == 0)):
                            ## time to run the checks again from this section
                            x = dict(CHECKS.items(section))
                            CURS = conn.cursor()
                            for key, sql  in sorted(x.items()):
                                if sql and key != "minutes":
                                    # printf ("%s DEBUG Running %s.%s\n", \
                                    # datetime.datetime.fromtimestamp(time.time()), section, key)
                                    try:
                                        QUERYCOUNTER += 1
                                        sqltimeout = threading.Timer(SQLTIMEOUT, conn.cancel)
                                        sqltimeout.start()
                                        START = timer()
                                        CURS.execute(sql)
                                        startf = timer()
                                        # output for the query must include the
                                        #        complete key and value
                                        rows = CURS.fetchall()
                                        if os.path.exists(OUT_FILE):
                                            OUTF = open(OUT_FILE, "a")
                                        else:
                                            OUTF = open(OUT_FILE, "w")
                                        if "discover" in section:
                                            OBJECTS_LIST = []
                                            for row in rows:
                                                d = collections.OrderedDict()
                                                for col in range(0, len(CURS.description)):
                                                    d[CURS.description[col][0]] = row[col]
                                                OBJECTS_LIST.append(d)
                                            ROWS_JSON = '{\"data\":'+json.dumps(OBJECTS_LIST)+'}'
                                            # printf ("DEBUG lld key: %s json: %s\n", key,
                                            #          ROWS_JSON)
                                            output(HOSTNAME, key, ROWS_JSON)
                                            output(HOSTNAME, ME[0] + "[query," + section + "," + \
                                              key + ",status]", 0)
                                        else:
                                            if  rows and len(rows[0]) == 2:
                                                for row in rows:
                                                    # printf("DEBUG zabbix_host:%s zabbix_key:%s " +
                                                    # "value:%s\n", HOSTNAME, row[0], row[1])
                                                    output(HOSTNAME, row[0], row[1])
                                                output(HOSTNAME, ME[0] + "[query," + section + "," +
                                                       key + ",status]", 0)
                                            elif not rows:
                                                output(HOSTNAME, ME[0] + "[query," + section + "," +
                                                       key + ",status]", 0)
                                            else:
                                                printf('%s key=%s.%s zbxORA-%d: ' +
                                                       'SQL format error: %s\n',
                                                       datetime.datetime.fromtimestamp(time.time()),
                                                       section, key, 2, "expect key,value pairs")
                                                output(HOSTNAME, ME[0] + "[query," + section + "," +
                                                       key + ",status]", 2)
                                        sqltimeout.cancel()
                                        fetchela = timer() - startf
                                        ELAPSED = timer() - START
                                        output(HOSTNAME, ME[0] + "[query," + section + "," +
                                               key + ",ela]", ELAPSED)
                                        output(HOSTNAME, ME[0] + "[query," + section + "," +
                                               key + ",fetch]", fetchela)
                                    except db.DatabaseError as oerr:
                                        if os.path.exists(OUT_FILE):
                                            OUTF = open(OUT_FILE, "a")
                                        else:
                                            OUTF = open(OUT_FILE, "w")
                                        ERROR, = oerr.args
                                        ELAPSED = timer() - START
                                        QUERYERROR += 1
                                        output(HOSTNAME, ME[0] + "[query," + section + "," + \
                                            key + ",status]", ERROR.code)
                                        output(HOSTNAME, ME[0] + "[query," + section + "," + \
                                            key + ",ela]", ELAPSED)
                                        printf('%s key=%s.%s ORA-%d: Db execution error: %s\n', \
                                            datetime.datetime.fromtimestamp(time.time()), \
                                            section, key, ERROR.code, ERROR.message.strip())
                                        # if ERROR.code in(28, 1012, 1013, 1041, 3113, 3114, 3135):
                                        # removed sql timeout as reason to start a new session
                                        if ERROR.code in(28, 1012, 1041, 3113, 3114, 3135):
                                            raise
                            # end of a section ## time to run the checks again from this section
                            output(HOSTNAME, ME[0] + "[query," + section + ",,ela]",
                                   timer() - SectionTimer)
                # dump metric for summed elapsed time of this run
                output(HOSTNAME, ME[0] + "[query,,,ela]",
                       timer() - RUNTIMER)
                output(HOSTNAME, ME[0] + "[cpu,user]",
                       resource.getrusage(resource.RUSAGE_SELF).ru_utime)
                output(HOSTNAME, ME[0] + "[cpu,sys]",
                       resource.getrusage(resource.RUSAGE_SELF).ru_stime)
                output(HOSTNAME, ME[0] + "[mem,maxrss]",
                       resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
                # passed all sections
                if ((NOWRUN - STARTTIME) % 3600) == 0:
                    gc.collect()
                    # dump stats
                    printf("%s connect %d times, %d fail; started %d queries, " +
                           "%d fail memrss:%d user:%f sys:%f\n",
                           datetime.datetime.fromtimestamp(time.time()),
                           CONNECTCOUNTER, CONNECTERROR, QUERYCOUNTER, QUERYERROR,
                           resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                           resource.getrusage(resource.RUSAGE_SELF).ru_utime,
                           resource.getrusage(resource.RUSAGE_SELF).ru_stime)
                # now pass data to zabbix, if possible
                if TO_ZABBIX_METHOD == "zabbix_sender":
                    STOUT = open(OUT_FILE + ".log", "w")
                    RESULT = subprocess.call(TO_ZABBIX_ARGS.split(), \
                        shell=False, stdout=STOUT, stderr=STOUT)
                    if RESULT not in(0, 2):
                        printf("%s zabbix_sender failed: %d\n", \
                            datetime.datetime.fromtimestamp(time.time()), RESULT)
                    else:
                        OUTF.close()
                        # create a datafile / day
                        if datetime.datetime.now().strftime("%H:%M") < "00:10":
                            TOMORROW = datetime.datetime.now() + datetime.timedelta(days=1)
                            Z = open(OUT_FILE + "." + TOMORROW.strftime("%a"), 'w')
                            Z.close()

                        with open(OUT_FILE + "." + datetime.datetime.now().strftime("%a"), \
                            'a') as outfile:
                            with open(OUT_FILE, "r") as infile:
                                outfile.write(infile.read())
                        OUTF = open(OUT_FILE, "w")

                    STOUT.close()

                # OUTF.close()
                if CRASH > 0:
                    printf("%s crashing due to error %d\n", \
                        datetime.datetime.fromtimestamp(time.time()), \
                        CRASH)
                    sys.exit(CRASH)
                # try to keep activities on the same starting second:
                SLEEPTIME = 60 - ((int(time.time()) - STARTTIME) % 60)
                # printf ("%s DEBUG Sleeping for %d seconds\n", \
                    # datetime.datetime.fromtimestamp(time.time()), SLEEPTIME)
                for i in range(SLEEPTIME):
                    time.sleep(1)
                CONMINS = CONMINS + 1 # not really mins since the checks could
                #                       have taken longer than 1 minute to complete
    except db.DatabaseError as oerr:
        ERROR, = oerr.args
        ELAPSED = timer() - START
        if ERROR.code not in (1012, 1013, 1041, 3114):
            # from a killed session, crashed instance or similar
            CONNECTERROR += 1
            output(HOSTNAME, ME[0] + "[connect,status]", ERROR.code)
        output(HOSTNAME, ME[0] + "[uptime]", int(timer() - STARTTIME))
        if ERROR.code == 15000:
            printf('%s: connection error: %s for %s@%s %s\n', \
                datetime.datetime.fromtimestamp(time.time()), \
                ERROR.message.strip().replace('\n', ' ').replace('\r', ' '), \
                USERNAME, DB_URL, ROLE)
            printf('%s: asm requires sysdba role instead of %s\n', \
            datetime.datetime.fromtimestamp(time.time()), ROLE)
            raise
        if PERROR != ERROR.code:
            SLEEPC = 0
            SLEEPER = 1
            PERROR = ERROR.code
        INIF.close()
        SLEEPC += 1
        if SLEEPC >= 10:
            if SLEEPER <= 301:
                # don't sleep longer than 5 mins after connect failures
                SLEEPER += 10
            SLEEPC = 0
        printf('%s: (%d.%d)connection error: %s for %s@%s\n', \
            datetime.datetime.fromtimestamp(time.time()), \
            SLEEPC, SLEEPER, ERROR.message.strip().replace('\n', ' ').replace('\r', ' '), \
            USERNAME, DB_URL)
        time.sleep(SLEEPER)
    except (KeyboardInterrupt, SystemExit):
        OUTF.close()
        raise

OUTF.close()
