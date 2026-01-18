function mcurl
	if test -z "$MPROXY_URL"
		set -l MPROXY_URL "http://localhost:8080"
	end

	https_proxy="$MRPOXY_URL" curl --cacert ~/.mimtproxy/mitmproxy-ca-cert.pem $argv
end
