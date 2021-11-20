#!/usr/bin/python
#
# (c) copyright 2012-2015 dogtown@mare-system.de
# 
# License: GPL v2 
#
# dload: https://bitbucket.org/maresystem/dogtown-nagios-plugins
#
#
# credits / this plugin is inspired by:
#   check_nginx
#   yangzi2008@126.com
#   http://exchange.nagios.org/directory/Plugins/Web-Servers/nginx/check_nginx/details
#
#   check_nginx_status.pl
#   regis.leroy@gmail.com 
#   http://exchange.nagios.org/directory/Plugins/Web-Servers/nginx/check_nginx_status-2Epl/details 
#
#   gustavo chaves for findinx and fixing some bugs
#
# reimplemented by dogtown with more features
# 
# TODO:
#   - make -a work
#   - make -t test1,test2,test available w/ -w 1,2,3 -c 1,2,3
#
#

import string, urllib.request, urllib.error, urllib.parse, getopt, sys, time, os

version = "0.3.0.59 - rc-2 - 2015-02-02"

### default_values

# default status url
url     = "/nginx_status"

# default host to check
host    = "localhost"

# default nginx_poret; is set to 443 if -s is used
port    = 80

# default result-file for calculations, see -r/-n options
# set to 0 if you want to deactivate this feature globally,
#   can be turned on using -r if so
result_file = "/tmp/check_nginx.results"


# definitions


def usage():
   print("""
   
check_nginx_status is a Nagios-Plugin
to monitor nginx status and alerts on various values, 
based on teh output from HttpStubStatus - Module

it also creates, based on the returned values, a csv to store data


Usage:

    check_nginx_status [-H|--HOST] [-p|--port] [-u|--url] [-a|--auth] [-s|--ssl]
                       [-t|--test] [-w|--warning] [-c|--critical]
                       [-o|--output] [-r|--resultfile][-n|--noresult]
                       [-h|--help] [-v|--version] [-d|--debug]


Options:

  --help|-h)
    print check_nginx_status help

  --HOST|-H)
    Sets nginx host
    Default: localhost
  
  --port|-p)
    Sets connection-port 
    Default: 80/http, 443/https
  
  --ssl|-s)
    Turns on SSL
    Default: off
  
  --url|-u)
    Sets nginx status url path. 
    Default: /nginx_status
  
  --auth|-a)
    Sets nginx status BasicAuth user:password. 
    Default: off
    ***
  
  --test|-t)
    Sets the test(check)_value for w/c
    if used, -w/-c is mandatory
    Default: checktime
    possible Values:

        active_conns    -> active connections
        accepts_err     -> difference between accepted and 
                           handled requests (should be 0)
        requests        -> check for requests/connection
        reading         -> actual value for reading headers
        writing         -> value for active requests
        waiting         -> actual keep-alive-connections
        checktime       -> checks if this check need more than
                           given -w/-c milliseconds 
        
    --calculated checks ---------------
        rps             -> requests per seconds
        cps             -> connections per second
        dreq            -> delta requests to the previous one
        dcon            -> delta connections to the previous one
        
        these checks are calculated at runtime with a timeframe 
        between the latest and the current check; time is 
        extracted from the timestamp of the result_file
        
        to disable calculation (no files are written) use -n; 
        you cannot use -t [rps,cps,dreq,dcon] with -n; this
        will raise an error and the plugin returns UNKNOWN

        see -r - option for an alternate filepath for temporary results
        
  --warning|-w)
    Sets a warning level for selected test(check)
    Default: off
  
  --critical|-c)
    Sets a critical level for selected test(check)
    Default: off
    
  --debug|-d)
    turn on debugging - messages (use this for manual testing, 
    never via nagios-checks; beware of the messy output
    Default: off 
    
  --version|-v)
    display version and exit

  --output|-o)
    output only values from selected tests in perfdata; if used w/out -t
    the check returns the value for active connections

  --resultfile|-r)
    /path/to/check_nginx.results{.csv}
    please note, beside the values from the actual check 
    (eg.g check_nginx.results) a second
    file is created, if not existent, and written on each plugin-run
    (check_nginx.results.csv), containign a historic view on all 
    extracted values
    default: /tmp/check_nginx.results{.csv}

  --noresult|-n)
    never write a results-file; CANNOT be used with calculated checks 
    -t [rps|cps|dreq|dcon] 
    default: off 
    
    *** ) -> please dont use this option, not implemented or not functional

Examples:

    just get all perfdata, url is default (/nginx_status)
    ./check_nginx_status --HOST www.example.com 

    just get active connections perfdata
    ./check_nginx_status -H www.example.com -o 
    
    check for plugin_checktime, error > 10ms (warning) or 50ms (error) and output
    only perfdata for that values
    ./check_nginx_status -H www.example.com -u /status  -w 10 -c 50 -o
    
    check for requests per second, alert on > 300/1000 active connections
    ./check_nginx_status -H www.example.com -u /status -t rps -w 300 -c 1000

    Check for accepts_errors
    ./check_nginx_status -H www.example.com -t accepts_err -w 1 -c 50

Performancedata:
    
    NginxStatus.Check OK | ac=1;acc=64; han=64; req=64; err=0; rpc=1; rps=0; cps=0; dreq=1; 
                           dcon=1; read=0; writ=1; wait=0; ct=6ms;

        ac      -> active connections
        acc     -> totally accepted connections
        han     -> totally handled connections
        req     -> total requests
        err     -> diff between acc - han, thus errors
        rpc     -> requests per connection (req/han) 
        rps     -> requests per second (calculated) from last checkrun vs actual values
        cps     -> connections per (calculated) from last checkrun vs actual values
        dreq    -> request-delta from last checkrun vs actual values
        dcon    -> accepted-connection-delta from last checkrun vs actual values 
        read    -> reading requests from clients
        writ    -> reading request body, processes request, or writes response to a client
        wait    -> keep-alive connections, actually it is ac - (read + writ)
        ct      -> checktime (connection time) for this check

    rpc/rps/dreq/dcon are always set to 0 if -n is used

Nginx-Config
    be sure to have your nginx compiled with Status-Module
    (--with-http_stub_status_module), you might want to test 
    your installation with nginx -V             
    http://wiki.nginx.org/HttpStubStatusModule

    location /nginx_status {
        stub_status on;
        access_log   off;
        allow 127.0.0.1;
        deny all;
    }

    
Requirements:

    nginx compiled with HttpStubStatusModule (see Nginx-Config)

    python 2.x
    this plugin is not yet compatible with python 3.x, 
    but should be converted easily, using 2to3

Docs & Download:

        https://bitbucket.org/maresystem/dogtown-nagios-plugins
    
            """)

def ver():
    print("""
check_nginx_status
    version : %s
    
    usage   : check_nginx_status -h
    
    """ % version)

def print_debug(dtext):
    if debug == 1:
        print("[d] %s" % dtext)
    return(0)


def calculate():
    rps = cps = dreq = dcon = 0
    now = int(time.time())
    if result_file != 0:
        if not os.path.isfile(result_file):
            print_debug("no result_file found, creating with next run :: %s " % result_file)
        else:
#~ 

            try:
                f = open(result_file, "r")
                ro = f.readline().split(";")
                f.close()
                o_ac    = int(ro[0])
                o_acc   = int(ro[1])
                o_han   = int(ro[2])
                o_req   = int(ro[3])
                o_err   = int(ro[4])
                o_rpc   = int(ro[5])
                o_rps   = int(ro[6])
                o_cps   = int(ro[7])
                o_dreq  = int(ro[8])
                o_dcon  = int(ro[9])
                o_read  = int(ro[10])
                o_writ  = int(ro[11])
                o_wait  = int(ro[12])
                o_ct    = int(ro[13])
                last    = int(os.path.getmtime(result_file))
                dtime   = now - last 
                if req >= o_req:
                  dreq = req - o_req
                else:
                  dreq = req                
                rps     = int(dreq / dtime)
                if acc >= o_acc:
                  dcon = acc - o_acc
                else:
                  dcon = acc
                cps     = int(dcon / dtime)

            except:
                print_debug("cannot read/process result_file :: %s \n use -r" % result_file)
                #return(rps, cps, dreq, dcon)
            
            
    else:
        
        if test in ("rps", "cps", "dreq", "dcon"):
            print("NginxStatus.%s UNKNONW - noresult selected (-n), cannot calculate test_results" % (test))
            sys.exit(3)
        
        print_debug("noresult selected, return 0_values")
        return(rps, cps, dreq, dcon)
            

    print_debug("writing result_file -> %s" % result_file)
    try:
        f = open(result_file, "w")
        f.write("%s; %s; %s; %s; %s; %s; %s; %s; %s; %s; %s; %s; %s; %s;\n" % (ac, acc, han, req, err, rpc, rps, cps, dreq, dcon, read, writ, wait, ct))
        f.close()
    except:
        print_debug("cannot create result_file :: %s \n use -r" % result_file)
        return(rps, cps, dreq, dcon)
    csv = "%s.csv" % result_file
    if not os.path.isfile(csv):
        try:
            print_debug("creating result_file.csv -> %s" % result_file)
            f = open(csv, "w")
            f.write(""""timestamp"; "active conns"; "accepted"; "handled"; "requests"; "req_errors"; "reqs per conn"; "reqs per sec"; "conns per sec"; "delta reqs"; "delta conns"; "reading"; "writing"; "waiting"; "checktime"; \n""")
        except:
            print("ERR.cannot create result_file.csv :: %s \n use -r" % csv)

    print_debug("writing result_file.csv -> %s.csv" % result_file)
    try:
        f = open(csv, "a")
        f.write("%s; %s; %s; %s; %s; %s; %s; %s; %s; %s; %s; %s; %s; %s; %s;" % (now, ac, acc, han, req, err, rpc, rps, cps, dreq, dcon, read, writ, wait, ct))
        f.close()
    except:
        print("ERR.cannot write result_file.csv :: %s \n use -r" % csv) 

    return(rps, cps, dreq, dcon)


#### main 

exot = 0
ssl = 0
debug = 0
test = 0
w = c = 0
output = 0
user = passwd = 0
msg = "CheckNginx - UNKNOWN"
perfdata = ""


try:
    iv = sys.argv[1]
except:
    print("""
    
usage: check_nginx_status -h

-----------------------------------------------------""")
    usage()
    sys.exit(3)
    

try:
    options,args = getopt.getopt(sys.argv[1:],"ndovDshH:p:u:p:w:c:t:r:",["help","SSL","Debug","HOST","port","auth","test","url","warning","critical", "output", "resultfile", "noresult"])

except getopt.GetoptError:
    usage()
    sys.exit(3)

for name,value in options:

    if name in ("-H","--HOST"):
        host = "%s" % value

    elif name in ("-u","--url"):
        url = value

    elif name in ("-a","--auth"):
        user, passwd = value.split(":")

    elif name in ("-s","--ssl"):
        ssl = 1

    elif name in ("-r","--resultfile"):
        result_file = "%s" % value

    elif name in ("-t","--test"):
        test = "%s" % value 

    elif name in ("-d","--debug"):
        debug = 1

    elif name in ("-o","--output"):
        output = 1

    elif name in ("-n","--noresult"):
        result_file = 0

    elif name in ("-p","--port"):
        try:
            port = int(value)
        except:
            print("""%s Usage.ERROR - -p [PORT] must be an Integer """ % msg)
            exot = 3

    elif name in ("-w","--warning"):
        try:
            w = int(value)
        except:
            print("""%s Usage.ERROR -w [WARNING] must be an Integer    """ % msg)
            exot = 3

    elif name in ("-c","--critical"):
        try:
            c = int(value)
        except:
            print("""%s Usage.ERROR -c [CRITICAL] must be an Integer    """% msg)
            exot = 3

    elif name in ("-v","--version"):
        ver()
        sys.exit(0)
    
    else:
        usage()
        ver()
        sys.exit(0)

if exot != 0:
    sys.exit(exot)

# creating test-url

if host.find("http") > -1:
    print("""%s Usage.ERROR - use -H [hostname], NOT -H [http://hostname] (%s)""" % (msg, host))
    sys.exit(3)

if ssl == 1:
    turl = "https://%s" % host
    print_debug("setting HTTP**S**")
else:
    turl = "http://%s" % host
    print_debug("setting HTTP")


if port != 80:
    turl = "%s:%s" % (turl, port)
    print_debug("setting Port: %s" % port)

curl = "%s%s" % (turl, url)
print_debug("final url to fetch: %s" % curl)


# start_time for checktime-calculation    
st = time.time()



try:

    req = urllib.request.Request(curl)
    response = urllib.request.urlopen(req)
    status = response.readlines()
    print_debug("returned_status from url: \n    %s" % "    ".join(status))
    response.close()
    #~ if 'user' in dir() and 'passwd' in dir():
        #~ passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
        #~ passman.add_password(None, curl, user, passwd)
        #~ authhandler = urllib2.HTTPBasicAuthHandler(passman)
        #~ opener = urllib2.build_opener(authhandler)
        #~ urllib2.install_opener(opener)


# TODO: http://stackoverflow.com/questions/2712524/handling-urllib2s-timeout-python
except Exception:
   print("%s: Error while getting Connection :: %s " % (msg, curl))
   sys.exit(3)



if len(status) == 0:
   print("%s: No values found in %s " % (msg , curl))
   sys.exit(3)

# end_time for checktime-calculation    
et = time.time()

try:
    ct = int((et - st)*1000)
    l1 = status[0]
    ac = int(l1.split(":")[1].strip())
    l2 = status[2]
    acc, han, req = l2.split()
    acc = int(acc)
    han = int(han)
    req = int(req)
    err = acc - han
    rpc = int(req/han)
    l3 = status[3]
    read = int((l3.split("Reading:")[1]).split()[0])
    writ = int((l3.split("Writing:")[1]).split()[0])
    wait = int((l3.split("Waiting:")[1]).split()[0])

except:
   print("%s: Error while trying to convert values from status_url %s " % (msg , curl))
   for line in status:
       print("  :: %s" % line.strip())
   sys.exit(3)

# calculate results, if wanted

rps, cps, dreq, dcon = calculate()
    
# creating needed output


print_debug("""-- status-report (perfdata)---

active_conns    :   %s
accepted conns  :   %s    
handled         :   %s
requests        :   %s
accept_errors   :   %s
req per conn    :   %s
req per second  :   %s
conn per second :   %s
delta requests  :   %s
delta conns     :   %s
reading         :   %s
writing         :   %s
waiting         :   %s

checktime       :   %s ms

""" % (ac, acc, han, req, err, rpc, rps, cps, dreq, dcon, read, writ, wait, ct  )) 


#~ if test == 0:
    #~ if w == 0 or c == 0:
        #~ pass
    #~ else:
        #~ test = "checktime"

if test != 0:
    if w == 0:
        print("""Usage.ERROR :: -w [WARNING] must be set and Integer (cannot be 0)""")
        sys.exit(3)
    
    if c == 0:
        print("""Usage.ERROR :: -c [CRITICAL] must be set and Integer (cannot be 0)""")
        sys.exit(3)
        
# default test_text
tt = "unknown"

# checking which test to perform
if test == 0:
    ta = ac
    tt = "Check"
elif test == "active_conns":
    ta = ac
    tt = "ActiveConnections"
elif test == "accepts_err":
    ta = err
    tt = "AcceptErrors"

elif test == "requests":
    ta = req
    tt = "Requests/Connection"


elif test == "reading":
    ta = read
    tt = "Reading"

elif test == "writing":
    ta = writ
    tt = "Writing"

elif test == "waiting":
    ta = wait
    tt = "Waiting"

# calculated checks
elif test == "rps":
    ta = rps
    tt = "Req_per_second"

elif test == "cps":
    ta = cps
    tt = "Conn_per_second"

elif test == "dreq":
    ta = dreq
    tt = "Delta_Requests"

elif test == "dcon":
    ta = dreq
    tt = "Delta_Conn"


else:
    ta = ct
    tt = "CheckTime"
    
print_debug("set test: %s" % tt)
dt = "NginxStatus.%s" % tt


# creating perfdata
if output == 1:
    if test == 0:
        perfdata="active_conns=%s;" % ta
    else:
        perfdata = "%s=%s;" % (test, ta)
else:
    perfdata = "ac=%s;acc=%s; han=%s; req=%s; err=%s; rpc=%s; rps=%s; cps=%s; dreq=%s; dcon=%s; read=%s; writ=%s; wait=%s; ct=%sms;"   % (ac, acc, han, req, err, rpc, rps, cps, dreq, dcon, read, writ, wait, ct  ) 

print_debug("perfdata: %s" % perfdata)


if test == 0:
    print("%s OK [ %s ] | %s" % (dt, ta,  perfdata))
    sys.exit(0)

if ta >= c:
    print("%s CRITICAL: %s | %s" % (dt, ta, perfdata))
    sys.exit(2)
    
elif ta >= w:
    print("%s WARNING: %s | %s" % (dt, ta, perfdata))
    sys.exit(1)

else:
    print("%s OK [ %s ] | %s" % (dt, ta, perfdata))
    


