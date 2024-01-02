#!/usr/bin/env perl

use LWP::UserAgent;

LWP::UserAgent->new()->post(
  "https://api.pushover.net/1/messages.json", [
  "token" => $ENV{'token'},
  "user" => $ENV{'user'},
  "message" => $ENV{'message'},
  "title" => $ENV{'title'},
]);

