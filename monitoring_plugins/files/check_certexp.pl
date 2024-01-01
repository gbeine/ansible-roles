#!/usr/bin/env perl

# $Id: check_certexp,v 1.9 2007/11/25 01:32:54 holger Exp $
#
# Check certificate expiry.
#
# Copyright (c) 2005 Holger Weiss <holger@CIS.FU-Berlin.DE>.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.

use warnings;
use strict;
use Socket;
use Getopt::Long;
use Net::SSLeay;
use Date::Manip;

use lib '/usr/lib/nagios/plugins';
use utils qw(%ERRORS $TIMEOUT &print_revision &support);
use vars qw($PROGNAME $PORT $CRIT $opt_H $opt_V $opt_c $opt_h $opt_i
            $opt_p $opt_t $opt_v $opt_w);

sub days_until_expiry ($$\@);
sub expiry_date ($$\@);
sub die_crit ($);
sub die_warn ($);
sub die_unknown ($);
sub print_usage ();
sub print_help ();
my ($issuer, $ssl_port, $warning, $critical, $timeout, $days, $suffix);
my @issuers;

$PROGNAME = 'check_certexp';
$PORT = 443;
$CRIT = 28;
$SIG{ALRM} = sub { die_unknown('Timeout'); };
$ENV{PATH} = '';
$ENV{ENV} = '';
$ENV{TZ} = 'CET';

Getopt::Long::Configure('bundling');
if (!GetOptions('V'   => \$opt_V, 'version'    => \$opt_V,
                'h'   => \$opt_h, 'help'       => \$opt_h,
                # actually, we won't produce any verbose output
                'v+'  => \$opt_v, 'verbose+'   => \$opt_v,
                'H=s' => \$opt_H, 'hostname=s' => \$opt_H,
                'c=i' => \$opt_c, 'critical=i' => \$opt_c,
                'i=s' => \$opt_i, 'issuer=i'   => \$opt_i,
                'p=i' => \$opt_p, 'port=i'     => \$opt_p,
                't=i' => \$opt_t, 'timeout=i'  => \$opt_t,
                'w=i' => \$opt_w, 'warning=i'  => \$opt_w)) {
	print "Error processing command line options\n";
	print_usage();
	exit $ERRORS{UNKNOWN};
}
if ($opt_V) {
	print_revision($PROGNAME, '$Revision: 1.9 $ ');
	exit $ERRORS{OK};
}
if ($opt_h) {
	print_help();
	exit $ERRORS{OK};
}
unless ($opt_H) {
	print "No target host specified\n";
	print_usage();
	exit $ERRORS{UNKNOWN};
}
$critical = $opt_c ? $opt_c : $CRIT;
$warning = $opt_w ? $opt_w : $critical;
@issuers = split(/:/, $opt_i) if $opt_i;
if ($warning < $critical) {
	print "Warning smaller than critical threshold\n";
	print_usage();
	exit $ERRORS{UNKNOWN};
}
$ssl_port = $opt_p ? $opt_p : $PORT;
$timeout = $opt_t ? $opt_t : $TIMEOUT;
alarm($timeout);

$days = days_until_expiry($opt_H, $ssl_port, @issuers);
if ($days < 0) {
	$days =~ s/^-//;
	$suffix = 'days ago';
	$suffix .= " ($issuer)" if $issuer;
	die_crit("Certificate expired $days $suffix");
}
$suffix = 'days';
$suffix .= " ($issuer)" if $issuer;
die_crit("Certificate expires in $days $suffix") if $days < $critical;
die_warn("Certificate expires in $days $suffix") if $days < $warning;
print "Certificate expires in $days $suffix\n";
exit $ERRORS{OK};

sub days_until_expiry ($$\@) {
	my ($host, $port, $issuers_ref) = @_;

	(my $exp = expiry_date($host, $port, @$issuers_ref)) =~ s/ GMT//;
	int((&UnixDate(&ParseDate($exp), '%s') - time) / 86400);
}

sub expiry_date ($$\@) {
	my ($host, $port, $issuers) = @_;
	my ($buffer, $iaddr, $paddr, $ctx, $ssl, $crt, $end, $str);

	# connect socket
	$iaddr = inet_aton($host)
	    || die_unknown("Invalid hostname/address: $host");
	$paddr = sockaddr_in($port, $iaddr);
	socket(SOCK, PF_INET, SOCK_STREAM, getprotobyname('tcp'))
	    || die_unknown("Socket error: $!");
	connect(SOCK, $paddr) || die_unknown("Error connecting to $host: $!");

	# initialize SSL
	Net::SSLeay::load_error_strings();
	Net::SSLeay::SSLeay_add_ssl_algorithms();
	Net::SSLeay::randomize();

	$ctx = Net::SSLeay::CTX_new();
	$ssl = Net::SSLeay::new($ctx);

	Net::SSLeay::set_tlsext_host_name($ssl, $host);
	Net::SSLeay::set_fd($ssl, fileno(SOCK));
	Net::SSLeay::connect($ssl)
		|| die_unknown(Net::SSLeay::print_errs('SSL connect failed') or
		              'SSL connect failed');

	# get certificate
	$crt = Net::SSLeay::get_peer_certificate($ssl)
		|| die_unknown(Net::SSLeay::print_errs(
		              'Cannot get peer certificate') or
		              'Cannot get peer certificate');

	# get expiry date (string)
	$end = Net::SSLeay::X509_get_notAfter($crt);
	$str = Net::SSLeay::P_ASN1_UTCTIME_put2string($end);

	if (@$issuers) {
		# get issuer name (string)
		$issuer = Net::SSLeay::X509_NAME_oneline(
		          Net::SSLeay::X509_get_issuer_name($crt));

		$issuer =~ s/\/.*CN=([^\/]+).*/$1/;
		die_crit("CN '$issuer' doesn't match: " . join(':', @issuers))
			if not grep($issuer eq $_, @$issuers);
	}

	# cleanup
	Net::SSLeay::free($ssl);
	Net::SSLeay::CTX_free($ctx);
	close SOCK;

	$str;
}

sub die_unknown ($) {
	printf "%s\n", shift;
	exit $ERRORS{UNKNOWN};
}

sub die_warn ($) {
	printf "%s\n", shift;
	exit $ERRORS{WARNING};
}

sub die_crit ($) {
	printf "%s\n", shift;
	exit $ERRORS{CRITICAL};
}

sub print_usage () {
	print "Usage: $PROGNAME -H host [-p port] [-i issuer] [-w warn]\n" .
	      "       [-c crit] [-t timeout] [-v]\n";
}

sub print_help () {
	print_revision($PROGNAME, '$Revision: 1.9 $');
	print "Copyright (c) 2006 Holger Weiss\n\n";
	print "Check certificate expiry date.\n\n";
	print_usage();
	print <<EOF;

 -H, --hostname=ADDRESS
    Host name or IP address
 -p, --port=INTEGER
    Port number (default: $PORT)
 -i, --issuer=NAME:NAME
    Certificate issuer name(s)
 -w, --warning=INTEGER
    WARNING if less than specified number of days until expiry (default: $CRIT)
 -c, --critical=INTEGER
    CRITICAL if less than specified number of days until expiry (default: $CRIT)
 -t, --timeout=INTEGER
    Seconds before connection times out (default: $TIMEOUT)
 -v, --verbose
    Show details for command-line debugging (Nagios may truncate output)

EOF
	support();
}
