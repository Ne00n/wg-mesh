# API

Currently the webservice / API is exposed at ::8080, without TLS, use a reverse proxy for TLS<br>
You can find an example config file for nginx in configs/

Internal requests from 10.0.0.0/8 don't need a token (connectivity, connect and update).<br>
- /connectivity needs a valid token, otherwise will refuse to provide connectivity info<br>
- /connect needs a valid token, otherwise the service will refuse to setup a wg link<br>
- /update needs a valid wg public key and link name, otherwise it will not update the wg link<br>
- /disconnect needs a valid wg public key and link name, otherwise will refuse to disconnect a specific link<br>