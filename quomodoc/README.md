# Quomodoc

Quomodoc hosts arbitrary HTML documents in a script-disabled iframe and lets readers attach comments to highlighted text.

## Routes

- `GET /quomodoc/` — document index and browser upload form
- `GET /quomodoc/docs/<slug>` — annotation workspace
- `POST /quomodoc/api/documents` — password-protected JSON or multipart upload
- `GET /quomodoc/api/documents` — document listing
- `POST /quomodoc/api/documents/<slug>/comments` — add an anchored comment
- `GET /quomodoc/health` — health check

JSON upload shape:

```json
{
  "password": "<upload password>",
  "title": "Document title",
  "slug": "optional-slug",
  "html": "<!doctype html>..."
}
```

The service stores only the SHA-256 verifier in `/etc/quomodoc.env`; plaintext is not persisted. Set it interactively with `python set_password.py` and restart the service.

Uploaded scripts are disabled by iframe sandboxing and Content Security Policy. Styles, data URLs, and HTTPS-hosted media remain available.
