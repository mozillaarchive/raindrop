package Raindrop::Router;
use Apache2::Const qw(DECLINED OK HTTP_UNAUTHORIZED);
use Apache2::Log qw();
use Apache2::RequestRec ();
use Apache2::RequestUtil ();
use Apache2::Connection     ();
use Apache2::ConnectionUtil ();
use Time::HiRes qw(gettimeofday tv_interval);

use APR::Table ();
use LWP::Simple qw(get);
use JSON qw(from_json to_json);

use strict;

my $user_db_url = "http://localhost:5984/raindrop-users-v1";

use CHI;
my $cache = CHI->new(
  'driver' => 'File',
  'namespace' => __PACKAGE__,
  'expires_in' => 60,
  # Driver specific
  'root_dir' => '/mnt/cache/Raindop-Proxy',
  'key_digest' => 'MD5',
);

sub authz : method {
    my ($self, $r) = @_;

    my $db = $self->lookup_db($r);
    my $backend = $self->lookup($r, $db);

    my $info = $r->pnotes('raindrop-user-info');

    use List::Util qw(first);
    if (exists $info->{ids} and UNIVERSAL::isa($info->{ids}, 'ARRAY') ) {
        my @ids = @{$info->{ids}};
        my $user = $r->user;
        $r->err_headers_out->set('X-Raindrop-User' => $user || 'Nobody');
        if ( grep { $_ eq $user } @ids ) {
            return OK;
        }
        else {
            $r->warn("Hi $user, this raindrop is limited to: @ids");
            $r->note_basic_auth_failure;
            return HTTP_UNAUTHORIZED;
        }
      }

    return DECLINED;  
}

sub lookup_db_by_id {
  my ($class, $r) = @_;
  my $user = $r->user;
  my $info_url = "$user_db_url/_design/users/_view/by-openid?key=%22$user%22";
  my $info;
  unless($info = $r->pnotes('raindrop-user-db') || $cache->get($info_url)) {
    my $data = get($info_url);
    my $json = from_json($data);
    if ($json && $json->{total_rows}) {
        $info = $json->{rows}[0]{value};
        $r->pnotes('raindrop-user-db' => $info);
        $cache->set($info_url, $info);
    }
  }
  if ($info && ! $r->pnotes('raindrop-user-db')) {
        $r->pnotes('raindrop-user-db' => $info);
  }

  return $info; 
}

sub lookup {
  my ($self, $r, $db) = @_;
  my $info_url = "$user_db_url/_design/users/_view/by-username?key=%22$db%22";
  my $info;

  unless($info = $r->pnotes('raindrop-user-info') || $cache->get($info_url)) {
    my $data = get($info_url);
    my $json = from_json($data);
    if ($json && $json->{total_rows}) {
        $info = $json->{rows}[0]{value};

        $r->pnotes('raindrop-user-info' => $info);
        $cache->set($info_url, $info);
    }
  }

  if ($info && ! $r->pnotes('raindrop-user-info')) {
        $r->pnotes('raindrop-user-info' => $info);
  }

  my $backend;
  if (exists $info->{backend}) {
      $backend = $info->{backend};
      if (not $info->{active}) {
         $r->warn("backend $backend marked inactive");
         $backend = "http://www.mozillamessaging.com";
      }
      if ($r->uri =~ m[^/raindrop-metrics/]) {
         $backend = $info->{'metrics-backend'};
         my $uri = $r->uri;
      }
  }
  else {
    $r->warn("Couldn't find a backend for $db") unless $db eq 'localhost';
  }

  $backend ||= $r->dir_config('RaindropFallbackBackend');


  return $backend;
}


sub lookup_db {
  my ($class, $r) = @_;

  my $host = $r->headers_in->get('Host');
  #XXX: Handle hosts like www.google.com
  my $db = "raindrop";

  if ($host ne '127.0.0.1') {
      $db = (split(/\./, $host))[0];
  }

  if ($db eq 'raindrop') {
      my $possible_db = $class->lookup_db_by_id($r);
      $db = $possible_db if $possible_db; 
  }

  return $db;
}

sub is_futon_call {
    my ($class, $r, $db) = @_;
    if ($r->unparsed_uri =~ m[^/_all_dbs$]) {
        $r->handler('modperl');
        $r->pnotes('raindrop-db' => $db);
        $r->push_handlers(PerlResponseHandler => 'Raindrop::Router->futon_call');
        return 1;
    }
return;
}

sub is_api_call {
    my ($class, $r) = @_;
    #Assumes lookup is cached already, somewhat bad
    if ($r->unparsed_uri =~ m[^/_api/]) {
        if (my $info = $r->pnotes('raindrop-user-info')) {
            if (my $gearmans = $info->{'gearmans'}) {
                $r->pnotes('raindrop-gearmans' => $gearmans);
                $r->handler('modperl');
                $r->push_handlers(PerlResponseHandler => 'Raindrop::Router->api_call');
                return 1;
            }
        }
    }
    return;
}

use Apache2::Request;
sub api_payload {
    my ($class, $r) = @_;
    my $uri = $r->uri;

    #cheat and stick the db name first
    my @path = split(m[/+], $uri);
    $path[0] = $class->lookup_db($r);
    
    my $req = Apache2::Request->new($r);
    my $body;
    if ($r->method eq 'POST') {
       if (my $cl = $r->headers_in->get('Content-Length')) {
           my $buffer;
           my $cnt = $r->read($buffer, $cl);
           $body = $buffer if $cnt == $cl;
        }
    }
    my %params;
    foreach my $k ($req->param) {
        $params{$k} = $req->param($k);
    }

    my $headers_in = $r->headers_in;
    my %headers;
    foreach my $k (keys %$headers_in) {
        $headers{$k} = $headers_in->{$k};
    }
    
    my $output = {
    "body" => "undefined",
    "form" => {},
    "headers" => {%{$r->headers_in}},
    "verb" => $r->method,
    "path" => \@path,
    "query" => \%params,
    "body" => $body,
};
  return $output;
}

sub futon_call {
    my ($class, $r) = @_;
    my $db = $r->pnotes('raindrop-db');
    $r->content_type('application/json');
    $r->print("[ '$db' ]");
    return OK;
}

sub api_call {
    my ($class, $r) = @_;

    $r->content_type('application/json');

    my $gearmans = $r->pnotes('raindrop-gearmans');

    my $gearman = Gearman::Client->new;
    $gearman->job_servers(@$gearmans);

    my $api_payload = $class->api_payload($r);
    my $payload = to_json($api_payload);

    my $start = [gettimeofday];

    my $retry = 0;
    my $res;
    while($retry < 3) {
      eval {
        $res = $gearman->do_task(apirunner => $payload, {
          #'retry_count' => 2,
          'high_priority' => 1,
        });
      };
      last if ($res and not $@);
      $retry++;
    }
    
    if ($retry == 3) {
      $r->warn("Tried $retry times to make gearman request, still failed : last error was $@");
      die;
    }

    my $end = [gettimeofday];
    my $elapsed = tv_interval($start, $end);
    
    my @api_path = @{$api_payload->{path}};
    my $api = join '/', @api_path[3..@api_path-1];
    my $db = $api_path[0];

    $r->warn("Gearman request for $db:$api took $elapsed secs (retry=$retry)");
    if ($retry > 0) {
      $r->err_headers_out->set('X-Gearman-Retry' => $retry);
    }


    $r->headers_out->add('Powered-by' => 'Gearman/' . $Gearman::Client::VERSION);
    $r->headers_out->add('X-Gearman-Elapsed' => $elapsed);

    $res = from_json($$res);

    my $status = $res->{code} || OK;

#    print STDERR Dumper($res); use Data::Dumper;

    if (my $headers = $res->{headers}) {
#        print STDERR Dumper($res); use Data::Dumper;
        while (my ($h,$v) = each %{$headers}) {
           $r->headers_out->add($h => $v);
        }
    }

    # Sometimes, we get nothing back when there is nothing found
    # json and front end expects "[]" in JSON
    $res = $res->{json} || [ ];
    
    if(!ref($res)) {
      $res = [ $res ];
    }

    $res = to_json($res);

    $r->print($res);

    return $status;
}

sub handler : method {
  my ($class, $r) = @_;
  my $host = $r->headers_in->get('Host');

  if($host eq 'localhost:8000') {
      return DECLINED;
  }

  my $db = $class->lookup_db($r);

  if ($class->is_api_call($r)) {
      return DECLINED;
  }

  if ($class->is_futon_call($r, $db)) {
      return DECLINED;
  }

  my $backend = $class->lookup($r, $db);

  my $real_url = $r->unparsed_uri;

  #XXX: encapsualtion fail, backend picking should fix this
  if ($real_url =~ m[/raindrop-metrics/]) {
      $real_url =~ s[/raindrop-metrics/][/];
  }

#  if ($real_url =~ m[^/$db/]) {
#      $r->warn("[$backend] Found db name $db in $real_url"); 
#      $real_url =~ s[/$db/][/]g;
#  }

  my $dst = "$backend$real_url";

  if ($real_url =~ m[^/_] && $real_url !~ m[^/_design/]) {
    $dst =~ s[/$db/][/]g; 
    $r->warn("[$backend] Top-level: $real_url sent to $dst");
  }

  if ($dst =~ m[/$db/$db/]) {
      $dst =~ s[/$db/][/]g;
      $r->warn("[$backend] Strip /$db/ from $real_url");
  }
  

  $r->proxyreq(1);
  $r->uri($dst);
  $r->warn("[$db] sending you to $dst [$backend:$db]") unless $host eq '127.0.0.1';

  $r->filename("proxy:$dst");
  $r->handler('proxy-server');

  if ($r->headers_in->get('Authorization')) {
    $r->warn("Authorization header detected");
    $r->headers_in->unset("Authorization");
  }

  return DECLINED;
}
1;
