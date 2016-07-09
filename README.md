Simple File Server
==

Caveats
==
This puts your development box available on public internet through ngrok. You've been warned.

Usage
===
Required: install and authorize ngrok
Set the following ENV 
```
NGROK_SUBDOMAIN=
```

Optionally set the following ENV variables, if left unset the pass will be generated pseudo-randomly.

```
BASIC_AUTH_USER=
BASIC_AUTH_PASSWORD=
```

Running It
===
```
forego start
```

# Post/Upload File
```
curl -X POST -F file=@txt.log https://$NGROK_SUBDOMAIN.ngrok.io
```
# Get File
```
curl https://$NGROK_SUBDOMAIN.ngrok.io/usage.txt > usage.txt
```

LICENSE
===

Work by those listed below is licensed respective to the terms they provide. See links for details.
Initial Credit: http://opensource.apple.com//source/python/python-3/python/Lib/SimpleHTTPServer.py?txt
File upload Credit: http://li2z.cn/?s=SimpleHTTPServerWithUpload written by bones7456
Basic Auth Credit: https://github.com/wonjohnchoi/Simple-Python-File-Server-With-Browse-Upload-and-Authentication
Polishing and Standardizing for production: @ZPH and governed by LICENSE file.
